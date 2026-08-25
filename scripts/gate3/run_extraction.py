"""Gate 3: retrieve and extract requirements live, then score the result.

This is the decision point the whole product rests on. Preflight's claim is
that it can read what a destination currently publishes and turn it into rules
that are safe to measure a film against. If a model cannot do that reliably on
two destinations whose specifications are published as plain tables, it will not
do it on harder sources, and the honest response is to say so.

Scoring is against the hand-transcribed ground truth in scripts/gate0. That
file was written by a human reading the same two pages, so agreement is
meaningful and disagreement is a real finding rather than a metric artefact.
"""

from __future__ import annotations

import sys as _sys

# Windows consoles default to cp1252. A report that crashes while
# printing a citation is worse than no report.
if hasattr(_sys.stdout, "reconfigure"):
    _sys.stdout.reconfigure(encoding="utf-8", errors="replace")

import json
import os
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
for sub in ("packages/contracts", "apps/agent", "scripts/gate0"):
    sys.path.insert(0, str(ROOT / sub))

from preflight_agent.extract import extract_rules  # noqa: E402
from preflight_agent.reconcile import build_pack, find_ambiguities  # noqa: E402
from preflight_agent.tools.parallel_search import (  # noqa: E402
    detect_drift,
    fetch_full_sources,
    machine_readability,
    search_destination_requirements,
)
from preflight_contracts.compare import (  # noqa: E402
    describe_rule,
    find_conflicts,
    rules_equivalent,
)
from preflight_contracts.rules import Severity  # noqa: E402
from seed_rule_packs import GROUND_TRUTH  # noqa: E402

OUT = ROOT / "out" / "gate3"

DESTINATIONS = [
    {
        "id": "berlinale",
        "name": "Berlinale festival and EFM screening media",
        "domains": {"berlinale.de"},
        "queries": [
            "Berlinale technical specifications festival media DCP ProRes",
            "Berlinale subtitles burned-in resolution frame rate bitrate",
        ],
    },
    {
        "id": "artdocfest",
        "name": "Artdocfest film festival",
        "domains": {"artdocfest.com"},
        "queries": ["Artdocfest technical requirements video audio subtitles loudness"],
    },
]


def load_env() -> dict[str, str]:
    values = {}
    env_file = ROOT / ".env"
    if env_file.exists():
        for line in env_file.read_text(encoding="utf-8").splitlines():
            line = line.strip()
            if line and not line.startswith("#") and "=" in line:
                key, _, value = line.partition("=")
                values[key.strip()] = value.strip()
    for key in ("PARALLEL_API_KEY", "GOOGLE_CLOUD_PROJECT", "GOOGLE_APPLICATION_CREDENTIALS",
                "GOOGLE_CLOUD_LOCATION", "VERTEX_MODEL"):
        if values.get(key):
            os.environ.setdefault(key, values[key])
    return values


def score(destination_id: str, extracted) -> dict[str, object]:
    """Compare extracted rules against the human transcription.

    Matching is on (assetType, field) rather than on exact operator and value,
    because two correct readings of 'from 20 to 30 Mbps' may legitimately differ
    in form. Value agreement is reported separately.
    """
    truth = GROUND_TRUTH[destination_id]
    truth_fields = {
        (r.asset_type.value, r.field_name): r
        for r in truth.rules if r.severity is not Severity.CONTEXT
    }
    found_fields = {
        (r.asset_type.value, r.field_name): r
        for r in extracted.rules if r.severity is not Severity.CONTEXT
    }

    matched = sorted(set(truth_fields) & set(found_fields))
    missed = sorted(set(truth_fields) - set(found_fields))
    extra = sorted(set(found_fields) - set(truth_fields))

    agreed, disagreed = [], []
    for key in matched:
        want, got = truth_fields[key], found_fields[key]
        if rules_equivalent(want, got):
            agreed.append(key)
        else:
            disagreed.append({
                "field": f"{key[0]}.{key[1]}",
                "groundTruth": describe_rule(want),
                "extracted": describe_rule(got),
            })

    recall = len(matched) / len(truth_fields) if truth_fields else 0.0
    exact = len(agreed) / len(truth_fields) if truth_fields else 0.0

    return {
        "truthRules": len(truth_fields),
        "extractedRules": len(found_fields),
        "matchedFields": len(matched),
        "exactAgreement": len(agreed),
        "recall": round(recall, 3),
        "exactRate": round(exact, 3),
        "missed": [f"{a}.{f}" for a, f in missed],
        "extra": [f"{a}.{f}" for a, f in extra],
        "disagreed": disagreed,
    }


def main() -> int:
    env = load_env()
    api_key = env.get("PARALLEL_API_KEY", "")
    project = env.get("GOOGLE_CLOUD_PROJECT", "")
    location = env.get("GOOGLE_CLOUD_LOCATION", "us-central1")
    model = env.get("VERTEX_MODEL", "gemini-2.5-pro")

    if not api_key or not project:
        raise SystemExit("PARALLEL_API_KEY and GOOGLE_CLOUD_PROJECT must be set in .env")

    from google import genai

    client = genai.Client(vertexai=True, project=project, location=location)

    OUT.mkdir(parents=True, exist_ok=True)
    report: dict[str, object] = {"model": model, "destinations": {}}
    packs = []
    all_scores = []

    for destination in DESTINATIONS:
        print(f"\n{'=' * 78}\n{destination['name']}\n{'=' * 78}")

        sources = search_destination_requirements(
            api_key=api_key,
            destination_name=destination["name"],
            official_domains=destination["domains"],
            extra_queries=destination["queries"],
        )
        tiers: dict[str, int] = {}
        for source in sources:
            tiers[source.trust_tier] = tiers.get(source.trust_tier, 0) + 1
        print(f"  retrieved {len(sources)} sources  tiers={tiers}")
        for source in sources:
            marker = "  official" if source.trust_tier == "A" else "  unverified"
            print(f"    [{source.trust_tier}]{marker:>13}  {source.host}")

        sources = fetch_full_sources(api_key=api_key, sources=sources)

        thin = [
            s for s in sources
            if s.may_create_mandatory_rule and machine_readability(s) < 0.25
        ]
        for source in thin:
            print(f"    note: {source.host} is official but carries little "
                  f"measurable specification text")

        usable = [s for s in sources if s.may_create_mandatory_rule]
        untrusted = [s for s in sources if not s.may_create_mandatory_rule]

        print(f"\n  extracting from {len(usable)} trusted sources "
              f"({len(untrusted)} withheld as unverified)")

        result = extract_rules(
            client=client,
            model=model,
            destination_name=destination["name"],
            sources=sources,   # all of them: tier enforcement happens per rule
        )

        pack = build_pack(destination["id"], 1, result.rules, result.evidence)
        packs.append(pack)

        required = [r for r in pack.rules if r.severity is Severity.REQUIRED]
        context = [r for r in pack.rules if r.severity is Severity.CONTEXT]
        print(f"  {len(pack.rules)} rules  ({len(required)} mandatory, "
              f"{len(context)} demoted to context by source tier)")
        print(f"  {len(result.rejected)} proposals rejected by the schema")

        ambiguities = find_ambiguities(pack.rules, pack.evidence)
        if ambiguities:
            print(f"\n  {len(ambiguities)} ambiguities - official sources disagree:")
            for a in ambiguities:
                print("   ", a.explain().replace("\n", "\n    "))

        if result.injection_attempts:
            print(f"\n  {len(result.injection_attempts)} sources contained "
                  f"instruction-shaped text:")
            for attempt in result.injection_attempts:
                print(f"    [{attempt['tier']}] {attempt['url']}")
                print(f"        {attempt['patterns'][:120]}")

        card = score(destination["id"], result)
        all_scores.append(card)
        print("\n  scored against human transcription:")
        print(f"    recall           {card['recall']:.0%}  "
              f"({card['matchedFields']}/{card['truthRules']} fields found)")
        print(f"    exact agreement  {card['exactRate']:.0%}")
        if card["missed"]:
            print(f"    missed           {', '.join(card['missed'])}")
        if card["disagreed"]:
            print("    disagreed:")
            for d in card["disagreed"]:
                print(f"      {d['field']}: truth={d['groundTruth']!r} "
                      f"extracted={d['extracted']!r}")

        report["destinations"][destination["id"]] = {
            "sources": [
                {"url": s.url, "tier": s.trust_tier, "hash": s.source_hash}
                for s in sources
            ],
            "rules": len(pack.rules),
            "mandatory": len(required),
            "rejected": result.rejected,
            "injectionAttempts": result.injection_attempts,
            "ambiguities": [a.explain() for a in ambiguities],
            "score": card,
            "packDigest": pack.digest(),
        }

    # ---- drift ------------------------------------------------------------
    previous_path = OUT / "source_hashes.json"
    previous = json.loads(previous_path.read_text()) if previous_path.exists() else {}
    current_all = []
    for destination in DESTINATIONS:
        for entry in report["destinations"][destination["id"]]["sources"]:
            current_all.append(entry)
    current_hashes = {e["url"]: e["hash"] for e in current_all}

    if previous:
        from types import SimpleNamespace
        drift = detect_drift(
            previous,
            [SimpleNamespace(url=u, source_hash=h) for u, h in current_hashes.items()],
        )
        changed = [d for d in drift if d["change"] != "new"]
        print(f"\n{'=' * 78}\nSPEC DRIFT SINCE LAST RETRIEVAL\n{'=' * 78}")
        if changed:
            for d in changed:
                print(f"  {d['change'].upper():12} {d['url']}")
        else:
            print("  no change in any previously retrieved source")
        report["drift"] = drift
    else:
        print("\n  baseline source hashes recorded - drift detection active from "
              "the next run")
    previous_path.write_text(json.dumps(current_hashes, indent=2), encoding="utf-8")

    # ---- cross-destination conflicts --------------------------------------
    conflicts = find_conflicts(packs)
    report["conflicts"] = conflicts
    print(f"\n{'=' * 78}\nCROSS-DESTINATION CONFLICTS (from live-extracted rules)"
          f"\n{'=' * 78}")
    for c in conflicts:
        print(f"  [{c['strength'].upper()}] {c['assetType']}.{c['field']}: "
              f"{c['destinations'][0]} {c['requirements'][0]} vs "
              f"{c['destinations'][1]} {c['requirements'][1]}")
    if not conflicts:
        print("  none found")

    (OUT / "gate3_report.json").write_text(
        json.dumps(report, indent=2, default=str), encoding="utf-8"
    )
    for pack in packs:
        (OUT / f"{pack.destination_id}_extracted.json").write_text(
            pack.to_json(), encoding="utf-8"
        )

    # ---- gate decision ----------------------------------------------------
    mean_recall = sum(s["recall"] for s in all_scores) / len(all_scores)
    no_tier_d_mandatory = all(
        pack.evidence[r.source_evidence_id].trust_tier.value in ("A", "B", "C")
        for pack in packs
        for r in pack.rules
        if r.severity is Severity.REQUIRED
    )
    every_rule_cited = all(
        r.source_evidence_id in pack.evidence for pack in packs for r in pack.rules
    )

    checks = {
        "recall against human transcription >= 0.60": mean_recall >= 0.60,
        "no mandatory rule from an unverified source": no_tier_d_mandatory,
        "every rule carries source evidence": every_rule_cited,
        "at least one destination produced mandatory rules": any(
            any(r.severity is Severity.REQUIRED for r in p.rules) for p in packs
        ),
    }

    print(f"\n{'=' * 78}\nGATE 3 DECISION\n{'=' * 78}")
    print(f"  mean recall: {mean_recall:.0%}")
    for label, ok in checks.items():
        print(f"  [{'x' if ok else ' '}] {label}")
    print(f"\n  report: {OUT / 'gate3_report.json'}")

    if all(checks.values()):
        print("\n  GATE 3 PASSES - live retrieval and extraction produce cited, "
              "tier-enforced rules.")
        return 0
    print("\n  GATE 3 FAILS - extraction is not reliable enough to build on.")
    return 1


if __name__ == "__main__":
    raise SystemExit(main())
