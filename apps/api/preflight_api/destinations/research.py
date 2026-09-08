"""Researching a destination nobody prepared in advance.

This is the difference between a product and a demo. Preflight shipped knowing
two festivals, because two rule packs had been retrieved by a script and
committed. A filmmaker sending a film to Sundance was simply out of luck, and
the claim that Preflight retrieves current published requirements was true only
of work done weeks earlier by somebody else.

So the same pipeline the script ran now runs when a person asks for it:

    Parallel Search  -> find the destination's own documentation
    Parallel Extract -> read those pages, including PDFs
    trust tiers      -> decided in Python, from the URL, never by the model
    Gemini           -> structure only the material that passed

The order matters and so does the direction. The model never chooses what to
read and never reaches the web itself; it is handed text that has already been
judged, and its output is validated against a closed schema before any of it
becomes a requirement. A blog post that happens to describe Sundance's
specification cannot become a rule that blocks somebody's delivery.

It takes minutes, so it runs in the background against a row that records how
far it has got, and the browser watches that row.
"""

from __future__ import annotations

import logging
import re
import threading
import uuid
from datetime import UTC, datetime

from preflight_contracts.models import (
    Destination,
    DestinationResearch,
    RulePackRow,
    RuleRow,
    SourceEvidenceRow,
)
from preflight_contracts.rules import SCHEMA_VERSION, Severity
from sqlalchemy import select
from sqlalchemy.orm import Session, sessionmaker

from ..core.config import get_settings

logger = logging.getLogger("preflight.research")

CONFIRMED = "CONFIRMED"

#: Hosts that describe festivals without speaking for them. A page here is
#: worth reading and worth showing, but it can never create a binding
#: requirement - that is decided by trust tier, and this list only keeps such
#: hosts from being mistaken for the destination's own domain when guessing it.
AGGREGATORS = {
    "filmfreeway.com", "withoutabox.com", "festagent.com", "fast.io",
    "wikipedia.org", "en.wikipedia.org", "imdb.com", "reddit.com",
    "medium.com", "youtube.com", "facebook.com", "x.com", "twitter.com",
}


def slugify(name: str) -> str:
    slug = re.sub(r"[^a-z0-9]+", "-", name.strip().lower()).strip("-")
    return slug[:60] or "destination"


def guess_official_domain(name: str, sources) -> str | None:
    """Which host actually belongs to this destination?

    Trust tier is assigned from the destination's own domain, so for a
    destination nobody has configured, that domain has to be established before
    anything can be trusted. It is inferred from the search results rather than
    invented: the most common non-aggregator host whose name shares a
    distinctive word with what the user typed.

    Returning None is a real answer. It means nothing found looks like the
    destination's own site, and therefore nothing may become mandatory.
    """
    words = {
        w for w in re.split(r"[^a-z0-9]+", name.lower())
        if len(w) > 3 and w not in {
            "film", "festival", "cinema", "international", "movie", "media",
            "official", "submission", "submissions", "technical", "the", "and",
            "for",
        }
    }
    if not words:
        return None

    counts: dict[str, int] = {}
    for source in sources:
        host = (source.url or "").split("/")[2:3]
        if not host:
            continue
        host = host[0].lower().removeprefix("www.")
        if host in AGGREGATORS or any(host.endswith("." + a) for a in AGGREGATORS):
            continue
        stem = host.split(".")[0]
        if any(w in stem or stem in w for w in words):
            counts[host] = counts.get(host, 0) + 1

    if not counts:
        return None
    return max(counts, key=lambda h: counts[h])


def _set(session: Session, job_id: uuid.UUID, **fields) -> None:
    job = session.get(DestinationResearch, job_id)
    if job is None:
        return
    for key, value in fields.items():
        setattr(job, key, value)
    session.commit()


def run_research(job_id: uuid.UUID, factory: sessionmaker) -> None:
    """The whole pipeline, against its own session.

    Every failure is written to the row rather than raised into a thread
    nobody is watching. A destination that cannot be researched is a normal
    outcome the product must state, not an exception.
    """
    settings = get_settings()

    with factory() as session:
        job = session.get(DestinationResearch, job_id)
        if job is None:
            return
        name = job.query

    try:
        from preflight_agent.extract import extract_rules
        from preflight_agent.reconcile import build_pack
        from preflight_agent.tools.parallel_search import (
            fetch_full_sources,
            search_destination_requirements,
        )
    except ImportError as exc:  # pragma: no cover - packaging failure
        with factory() as session:
            _set(session, job_id, state="FAILED",
                 failure_reason=f"research is not available in this deployment: {exc}",
                 finished_at=datetime.now(UTC))
        return

    if not settings.parallel_api_key:
        with factory() as session:
            _set(session, job_id, state="FAILED",
                 failure_reason="Retrieval is not configured in this deployment.",
                 finished_at=datetime.now(UTC))
        return

    try:
        with factory() as session:
            _set(session, job_id, state="SEARCHING",
                 progress="Searching for official documentation")

        # First pass with no known domain, purely to discover which host is the
        # destination's own.
        found = search_destination_requirements(
            api_key=settings.parallel_api_key,
            destination_name=name,
            official_domains=set(),
        )
        domain = guess_official_domain(name, found)

        if domain is None:
            with factory() as session:
                _set(session, job_id, state="NOTHING_FOUND",
                     rejected_sources=len(found),
                     failure_reason=(
                         "We couldn't verify an official technical specification "
                         "for this destination. Nothing we found appears to be "
                         "published by them, and Preflight will not turn a third "
                         "party's description into a requirement."
                     ),
                     finished_at=datetime.now(UTC))
            return

        # Second pass, now knowing whose site to trust. Tier is assigned here,
        # in Python, from the URL alone.
        sources = search_destination_requirements(
            api_key=settings.parallel_api_key,
            destination_name=name,
            official_domains={domain},
        )

        with factory() as session:
            _set(session, job_id, state="READING",
                 progress=f"Reading {len(sources)} pages from {domain}")

        sources = fetch_full_sources(api_key=settings.parallel_api_key, sources=sources)
        official = [s for s in sources if s.may_create_mandatory_rule]

        if not official:
            with factory() as session:
                _set(session, job_id, state="NOTHING_FOUND",
                     official_sources=0, rejected_sources=len(sources),
                     failure_reason=(
                         "We couldn't verify an official technical specification "
                         "for this destination. We found pages about it, but none "
                         "published by them."
                     ),
                     finished_at=datetime.now(UTC))
            return

        with factory() as session:
            _set(session, job_id, state="EXTRACTING",
                 official_sources=len(official),
                 rejected_sources=len(sources) - len(official),
                 progress=f"Reading the requirements in {len(official)} official "
                          f"{'page' if len(official) == 1 else 'pages'}")

        from google import genai

        client = genai.Client(
            vertexai=True,
            project=settings.google_cloud_project,
            location=settings.google_cloud_location,
        )
        # Only the sources that passed are given to the model. The rejected
        # ones are counted and shown, never extracted from.
        result = extract_rules(
            client=client,
            model=settings.vertex_model,
            destination_name=name,
            sources=official,
        )

        with factory() as session:
            destination = _upsert_destination(session, name, domain)
            version = _next_version(session, destination.id)
            pack = build_pack(destination.slug, version, result.rules, result.evidence)

            mandatory = [r for r in pack.rules if r.severity is Severity.REQUIRED]
            if not mandatory:
                _set(session, job_id, state="NOTHING_FOUND",
                     destination_id=destination.id,
                     official_sources=len(official),
                     total_rules=len(pack.rules),
                     failure_reason=(
                         "We reached this destination's own pages but could not "
                         "read any measurable delivery requirement from them. "
                         "Preflight will not guess what they expect."
                     ),
                     finished_at=datetime.now(UTC))
                return

            pack_row = _persist(session, destination, pack, result)
            _set(session, job_id, state="READY",
                 destination_id=destination.id,
                 rule_pack_id=pack_row.id,
                 official_sources=len(official),
                 rejected_sources=len(sources) - len(official),
                 total_rules=len(pack.rules),
                 mandatory_rules=len(mandatory),
                 progress=None,
                 finished_at=datetime.now(UTC))

    except Exception as exc:  # noqa: BLE001 - a thread must not die silently
        logger.exception("research failed for %s", name)
        with factory() as session:
            _set(session, job_id, state="FAILED",
                 failure_reason=f"The search could not be completed: {exc}"[:400],
                 finished_at=datetime.now(UTC))


def _upsert_destination(session: Session, name: str, domain: str) -> Destination:
    slug = slugify(name)
    row = session.scalar(select(Destination).where(Destination.slug == slug))
    if row is None:
        row = Destination(slug=slug, name=name.strip()[:200])
        session.add(row)
    row.official_domain = domain
    row.public = True
    row.requires_private_spec = False
    session.flush()
    return row


def _next_version(session: Session, destination_id: uuid.UUID) -> int:
    latest = session.scalar(
        select(RulePackRow.version)
        .where(RulePackRow.destination_id == destination_id)
        .order_by(RulePackRow.version.desc())
    )
    return (latest or 0) + 1


def _persist(session: Session, destination: Destination, pack, result) -> RulePackRow:
    """Store the pack exactly as the seeding script stores one.

    A researched pack is not a lesser artefact: it is versioned, digested and
    confirmed the same way, so everything downstream - pinning, comparison,
    dispositions, the passport - treats it identically.
    """
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

    evidence_rows: dict[str, SourceEvidenceRow] = {}
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
        evidence_rows[eid] = row

    for rule in pack.rules:
        evidence_row = evidence_rows.get(rule.source_evidence_id)
        if evidence_row is None:
            continue  # a rule without evidence cannot exist
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
    return pack_row


def start(job_id: uuid.UUID, factory: sessionmaker) -> None:
    """Run the pipeline off the request thread."""
    thread = threading.Thread(
        target=run_research, args=(job_id, factory), daemon=True,
        name=f"research-{job_id}",
    )
    thread.start()
