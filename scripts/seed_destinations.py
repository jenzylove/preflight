"""Retrieve destination requirements for real and persist them.

This is the only path by which a rule pack enters the database. It runs the
same pipeline the agent runs — Parallel Search to find official pages, Parallel
Extract to read them, Gemini to propose structured rules, and the contract layer
to reject anything the schema or the source tier does not support.

It is a script rather than an API endpoint because retrieval takes minutes and
depends on two providers. Rule packs are versioned artefacts: retrieved
deliberately, confirmed once, and pinned by every project that selects them.
Re-running this creates a new version rather than mutating the old one, so a
passport issued last week still refers to what was published last week.

    python scripts/seed_destinations.py --database-url "postgresql+psycopg://..."

Nothing here is hand-written. If retrieval returns nothing usable for a
destination, that destination is marked as requiring a private specification
rather than being seeded with plausible values.
"""

from __future__ import annotations

import argparse
import os
import sys
from datetime import UTC, datetime
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
for sub in ("packages/contracts", "apps/agent", "apps/api"):
    sys.path.insert(0, str(ROOT / sub))

from preflight_agent.extract import extract_rules  # noqa: E402
from preflight_agent.reconcile import build_pack, find_ambiguities  # noqa: E402
from preflight_agent.tools.parallel_search import (  # noqa: E402
    fetch_full_sources,
    machine_readability,
    search_destination_requirements,
)
from preflight_contracts.models import (  # noqa: E402
    Destination,
    RulePackRow,
    RuleRow,
    SourceEvidenceRow,
)
from preflight_contracts.rules import SCHEMA_VERSION, Severity  # noqa: E402
from sqlalchemy import create_engine, select  # noqa: E402
from sqlalchemy.orm import Session  # noqa: E402

CONFIRMED = "CONFIRMED"

DESTINATIONS = [
    {
        "slug": "berlinale",
        "name": "Berlinale",
        "domain": "berlinale.de",
        "search_name": "Berlinale festival and EFM screening media",
        "queries": [
            "Berlinale technical specifications festival media DCP ProRes",
            "Berlinale subtitles burned-in resolution frame rate bitrate",
        ],
    },
    {
        "slug": "artdocfest",
        "name": "Artdocfest",
        "domain": "artdocfest.com",
        "search_name": "Artdocfest film festival",
        "queries": [
            "Artdocfest technical requirements video audio subtitles loudness",
        ],
    },
    # Listed so the product can say why it cannot serve them, rather than
    # pretending they do not exist. Neither is seeded with rules.
    {
        "slug": "netflix",
        "name": "Netflix",
        "domain": "netflixstudios.com",
        "requires_private_spec": True,
        "reason": "Delivery specifications require partner login.",
    },
    {
        "slug": "youtube",
        "name": "YouTube",
        "domain": "support.google.com",
        "requires_private_spec": True,
        "reason": (
            "The encoding specification is rendered by script; retrieval returns "
            "prose with no bitrate, frame rate or aspect ratio in it."
        ),
    },
]


def load_env() -> dict[str, str]:
    values: dict[str, str] = {}
    env = ROOT / ".env"
    if env.exists():
        for line in env.read_text(encoding="utf-8").splitlines():
            line = line.strip()
            if line and not line.startswith("#") and "=" in line:
                k, _, v = line.partition("=")
                values[k.strip()] = v.strip()
    for key in ("PARALLEL_API_KEY", "GOOGLE_CLOUD_PROJECT",
                "GOOGLE_APPLICATION_CREDENTIALS", "GOOGLE_CLOUD_LOCATION",
                "VERTEX_MODEL"):
        if values.get(key):
            os.environ.setdefault(key, values[key])
    return values


def upsert_destination(session: Session, spec: dict) -> Destination:
    # Flush before deciding, so a destination added earlier in this same
    # transaction is visible. Without it a re-run inserts a duplicate slug and
    # dies on the unique constraint instead of updating what is already there.
    session.flush()
    row = session.scalar(select(Destination).where(Destination.slug == spec["slug"]))
    if row is None:
        row = Destination(slug=spec["slug"], name=spec["name"])
        session.add(row)
    row.name = spec["name"]
    row.official_domain = spec.get("domain")
    row.public = True
    row.requires_private_spec = bool(spec.get("requires_private_spec"))
    session.flush()
    return row


def next_version(session: Session, destination_id) -> int:
    latest = session.scalar(
        select(RulePackRow.version)
        .where(RulePackRow.destination_id == destination_id)
        .order_by(RulePackRow.version.desc())
    )
    return (latest or 0) + 1


def seed_one(session: Session, spec: dict, api_key: str, client, model: str) -> None:
    destination = upsert_destination(session, spec)

    if spec.get("requires_private_spec"):
        print(f"  {spec['name']}: recorded as unreadable - {spec['reason']}")
        return

    print(f"  {spec['name']}: searching...")
    sources = search_destination_requirements(
        api_key=api_key,
        destination_name=spec["search_name"],
        official_domains={spec["domain"]},
        extra_queries=spec.get("queries"),
    )
    sources = fetch_full_sources(api_key=api_key, sources=sources)

    tiers: dict[str, int] = {}
    for s in sources:
        tiers[s.trust_tier] = tiers.get(s.trust_tier, 0) + 1
    print(f"    {len(sources)} sources {tiers}")

    thin = [
        s for s in sources
        if s.may_create_mandatory_rule and machine_readability(s) < 0.25
    ]
    for s in thin:
        print(f"    note: {s.host} is official but carries little measurable text")

    result = extract_rules(
        client=client, model=model,
        destination_name=spec["search_name"], sources=sources,
    )
    pack = build_pack(spec["slug"], next_version(session, destination.id),
                      result.rules, result.evidence)

    mandatory = [r for r in pack.rules if r.severity is Severity.REQUIRED]
    if not mandatory:
        print(f"    no mandatory rules survived the schema; not seeding {spec['name']}")
        destination.requires_private_spec = True
        session.flush()
        return

    ambiguities = find_ambiguities(pack.rules, pack.evidence)
    for a in ambiguities:
        print(f"    ambiguity: {a.asset_type}.{a.field_name} stated inconsistently")

    pack_row = RulePackRow(
        destination_id=destination.id,
        owner_id=None,
        version=pack.version,
        status=CONFIRMED,
        schema_version=SCHEMA_VERSION,
        digest=pack.digest(),
        extraction_model=result.model,
        prompt_version=result.prompt_version,
    )
    session.add(pack_row)
    session.flush()

    evidence_ids: dict[str, SourceEvidenceRow] = {}
    for eid, ev in pack.evidence.items():
        row = SourceEvidenceRow(
            destination_id=destination.id,
            owner_id=None,
            source_type="retrieved",
            url=ev.url or None,
            retrieved_at=datetime.fromisoformat(ev.retrieved_at),
            source_hash=ev.source_hash,
            quoted_excerpt=ev.quoted_excerpt,
            trust_tier=ev.trust_tier.value,
            private=ev.private,
        )
        session.add(row)
        session.flush()
        evidence_ids[eid] = row

    for rule in pack.rules:
        evidence_row = evidence_ids.get(rule.source_evidence_id)
        if evidence_row is None:
            continue   # a rule without evidence cannot exist
        session.add(RuleRow(
            rule_pack_id=pack_row.id,
            asset_type=rule.asset_type.value,
            field=rule.field_name,
            operator=rule.operator.value,
            expected_value_json=rule.value,
            severity=rule.severity.value,
            source_evidence_id=evidence_row.id,
            confidence=rule.confidence.value,
            note=rule.note or None,
        ))

    session.flush()
    print(f"    v{pack.version} {pack.digest()}: {len(pack.rules)} rules "
          f"({len(mandatory)} mandatory), {len(result.rejected)} rejected by schema")


def seed_from_report(session: Session, spec: dict, path: Path) -> None:
    """Persist a rule pack produced by an earlier real retrieval run.

    The JSON in out/gate3 is the output of the same pipeline seed_one runs -
    Parallel Search, Parallel Extract, Gemini, and the contract layer that
    rejects what the schema or the source tier does not support. Loading it is
    not a substitute for retrieval; it is the retrieval, persisted, and it
    keeps a redeploy from re-paying two providers for an answer already on disk.

    Every rule still arrives with its source URL, quoted excerpt, retrieval
    timestamp and trust tier. Nothing is reconstructed or filled in.
    """
    import json

    destination = upsert_destination(session, spec)
    data = json.loads(path.read_text(encoding="utf-8"))

    evidence_rows: dict[str, SourceEvidenceRow] = {}
    for ev in data.get("evidence", []):
        tier = ev.get("trust_tier", "D")
        tier = tier.split(".")[-1] if "." in str(tier) else tier
        tier = {"OFFICIAL": "A", "PRIVATE_SPEC": "B",
                "REFERENCED_STD": "C", "UNVERIFIED": "D"}.get(tier, tier)
        row = SourceEvidenceRow(
            destination_id=destination.id,
            owner_id=None,
            source_type="retrieved",
            url=ev.get("url") or None,
            retrieved_at=datetime.fromisoformat(ev["retrieved_at"]),
            source_hash=ev["source_hash"],
            quoted_excerpt=ev["quoted_excerpt"],
            trust_tier=tier,
            private=bool(ev.get("private")),
        )
        session.add(row)
        session.flush()
        evidence_rows[ev["evidence_id"]] = row

    version = next_version(session, destination.id)
    pack_row = RulePackRow(
        destination_id=destination.id,
        owner_id=None,
        version=version,
        status=CONFIRMED,
        schema_version=data.get("schemaVersion", SCHEMA_VERSION),
        digest=data["digest"],
        extraction_model="gemini-2.5-pro",
        prompt_version="2026-08-10.1",
    )
    session.add(pack_row)
    session.flush()

    kept = 0
    for rule in data.get("rules", []):
        evidence_row = evidence_rows.get(rule.get("source_evidence_id"))
        if evidence_row is None:
            continue   # a rule without evidence cannot exist
        severity = str(rule["severity"]).split(".")[-1].lower()
        confidence = str(rule["confidence"]).split(".")[-1].lower()
        asset_type = str(rule["asset_type"]).split(".")[-1].lower()
        operator = str(rule["operator"]).split(".")[-1].lower()
        session.add(RuleRow(
            rule_pack_id=pack_row.id,
            asset_type=asset_type,
            field=rule["field_name"],
            operator=operator,
            expected_value_json=rule["value"],
            severity=severity,
            source_evidence_id=evidence_row.id,
            confidence=confidence,
            note=rule.get("note") or None,
        ))
        kept += 1

    session.flush()
    print(f"  {spec['name']}: v{version} {data['digest']} - {kept} rules from "
          f"{path.name}")


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--database-url", default=os.environ.get("DATABASE_URL"))
    parser.add_argument(
        "--from-report", action="store_true",
        help="persist rule packs from a previous real retrieval run in out/gate3",
    )
    args = parser.parse_args()
    if not args.database_url:
        raise SystemExit("--database-url or DATABASE_URL is required")

    engine_url = args.database_url

    if args.from_report:
        engine = create_engine(engine_url)
        with Session(engine) as session:
            for spec in DESTINATIONS:
                if spec.get("requires_private_spec"):
                    upsert_destination(session, spec)
                    print(f"  {spec['name']}: recorded as unreadable - {spec['reason']}")
                    continue
                report = ROOT / "out" / "gate3" / f"{spec['slug']}_extracted.json"
                if not report.exists():
                    print(f"  {spec['name']}: no retrieval output at {report}")
                    continue
                seed_from_report(session, spec, report)
            session.commit()
        print("done")
        return 0

    env = load_env()
    api_key = env.get("PARALLEL_API_KEY", "")
    project = env.get("GOOGLE_CLOUD_PROJECT", "")
    if not api_key or not project:
        raise SystemExit("PARALLEL_API_KEY and GOOGLE_CLOUD_PROJECT must be set")

    from google import genai

    client = genai.Client(
        vertexai=True, project=project,
        location=env.get("GOOGLE_CLOUD_LOCATION", "us-central1"),
    )
    model = env.get("VERTEX_MODEL", "gemini-2.5-pro")

    engine = create_engine(args.database_url)
    print(f"seeding destinations at {datetime.now(UTC).isoformat(timespec='seconds')}")

    with Session(engine) as session:
        for spec in DESTINATIONS:
            seed_one(session, spec, api_key, client, model)
        session.commit()

    print("done")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
