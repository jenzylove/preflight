"""Destination selection and rule-pack confirmation.

Rule packs are versioned artefacts, retrieved from a destination's published
documentation and confirmed by the person delivering to it. Retrieval is a
separate, slow, provider-dependent act; this router serves what retrieval
produced and records which version a project is being measured against.

Nothing here invents a requirement. If no confirmed rule pack exists for a
destination, the destination is offered as unavailable rather than served with
plausible defaults.
"""

from __future__ import annotations

import uuid
from datetime import datetime

from fastapi import APIRouter, Depends, HTTPException, Request, status
from preflight_contracts.state import ProjectState, TransitionError, transition_project
from pydantic import BaseModel, Field
from sqlalchemy import func, select
from sqlalchemy.orm import Session

from ..auth.identity import current_user, owned_project
from ..core.db import get_session
from ..core.models import (
    Destination,
    DestinationResearch,
    Project,
    ProjectDestination,
    RulePackRow,
    RuleRow,
    SourceEvidenceRow,
    User,
)

router = APIRouter(prefix="/v1", tags=["destinations"])

CONFIRMED = "CONFIRMED"


class SourceOut(BaseModel):
    url: str | None
    retrieved_at: datetime
    trust_tier: str
    excerpt: str


class DestinationOut(BaseModel):
    id: uuid.UUID
    slug: str
    name: str
    official_domain: str | None
    requires_private_spec: bool
    available: bool
    rule_pack_id: uuid.UUID | None
    rule_pack_version: int | None
    rule_pack_digest: str | None
    mandatory_rules: int
    total_rules: int
    sources: list[SourceOut]
    unavailable_reason: str | None = None


def _latest_confirmed_pack(destination_id: uuid.UUID, session: Session) -> RulePackRow | None:
    return session.scalar(
        select(RulePackRow)
        .where(
            RulePackRow.destination_id == destination_id,
            RulePackRow.status == CONFIRMED,
        )
        .order_by(RulePackRow.version.desc())
    )


def _describe(destination: Destination, session: Session) -> DestinationOut:
    pack = _latest_confirmed_pack(destination.id, session)

    if pack is None:
        return DestinationOut(
            id=destination.id, slug=destination.slug, name=destination.name,
            official_domain=destination.official_domain,
            requires_private_spec=destination.requires_private_spec,
            available=False, rule_pack_id=None, rule_pack_version=None,
            rule_pack_digest=None, mandatory_rules=0, total_rules=0, sources=[],
            unavailable_reason=(
                "This destination publishes its requirements in a form Preflight "
                "cannot retrieve. Upload the specification you hold instead."
                if destination.requires_private_spec
                else "No confirmed requirements have been retrieved for this "
                     "destination yet."
            ),
        )

    total = session.scalar(
        select(func.count()).select_from(RuleRow).where(RuleRow.rule_pack_id == pack.id)
    ) or 0
    mandatory = session.scalar(
        select(func.count()).select_from(RuleRow).where(
            RuleRow.rule_pack_id == pack.id, RuleRow.severity == "required"
        )
    ) or 0

    evidence_rows = session.scalars(
        select(SourceEvidenceRow)
        .join(RuleRow, RuleRow.source_evidence_id == SourceEvidenceRow.id)
        .where(RuleRow.rule_pack_id == pack.id)
        .distinct()
    ).all()

    # One entry per URL: several rules quoting the same page is corroboration,
    # not several sources.
    seen: dict[str, SourceOut] = {}
    for row in evidence_rows:
        if row.private or not row.url or row.url in seen:
            continue
        seen[row.url] = SourceOut(
            url=row.url,
            retrieved_at=row.retrieved_at,
            trust_tier=row.trust_tier,
            excerpt=row.quoted_excerpt[:300],
        )

    return DestinationOut(
        id=destination.id, slug=destination.slug, name=destination.name,
        official_domain=destination.official_domain,
        requires_private_spec=destination.requires_private_spec,
        available=True, rule_pack_id=pack.id, rule_pack_version=pack.version,
        rule_pack_digest=pack.digest, mandatory_rules=mandatory, total_rules=total,
        sources=list(seen.values()),
    )


@router.get("/destinations", response_model=list[DestinationOut])
def list_destinations(session: Session = Depends(get_session)) -> list[DestinationOut]:
    """Every destination Preflight knows about, available or not.

    Unavailable ones are listed with the reason rather than hidden, because
    "we cannot read this destination" is information a producer needs.
    """
    destinations = session.scalars(
        select(Destination).where(Destination.public.is_(True)).order_by(Destination.name)
    ).all()
    return [_describe(d, session) for d in destinations]


class SelectionIn(BaseModel):
    destination_ids: list[uuid.UUID] = Field(min_length=1, max_length=10)


class SelectionOut(BaseModel):
    selected: list[DestinationOut]
    project_state: str


@router.put(
    "/projects/{project_id}/destinations",
    response_model=SelectionOut,
    status_code=status.HTTP_200_OK,
)
def set_destinations(
    payload: SelectionIn,
    project: Project = Depends(owned_project),
    session: Session = Depends(get_session),
) -> SelectionOut:
    """Choose where this project is going, pinning the rule-pack version.

    Replaces the whole selection rather than merging, so removing a destination
    is possible and the stored set always matches what the user last saw.
    """
    chosen = session.scalars(
        select(Destination).where(Destination.id.in_(payload.destination_ids))
    ).all()
    if len(chosen) != len(set(payload.destination_ids)):
        raise HTTPException(status_code=404, detail="Not found")

    for destination in chosen:
        if _latest_confirmed_pack(destination.id, session) is None:
            raise HTTPException(
                status_code=status.HTTP_409_CONFLICT,
                detail=(
                    f"Preflight has no confirmed requirements for {destination.name}. "
                    "It cannot measure your files against rules it has not retrieved."
                ),
            )

    existing = session.scalars(
        select(ProjectDestination).where(ProjectDestination.project_id == project.id)
    ).all()
    for row in existing:
        session.delete(row)
    session.flush()

    for destination in chosen:
        pack = _latest_confirmed_pack(destination.id, session)
        session.add(ProjectDestination(
            project_id=project.id,
            destination_id=destination.id,
            rule_pack_id=pack.id if pack else None,
            confirmed_at=datetime.now(tz=None),
        ))

    try:
        project.state = transition_project(
            ProjectState(project.state), ProjectState.DESTINATIONS_CONFIRMED
        ).value
    except TransitionError:
        pass   # re-selecting later in the journey is allowed

    session.flush()
    return SelectionOut(
        selected=[_describe(d, session) for d in chosen],
        project_state=project.state,
    )


@router.get("/projects/{project_id}/destinations", response_model=SelectionOut)
def get_destinations(
    project: Project = Depends(owned_project),
    session: Session = Depends(get_session),
) -> SelectionOut:
    rows = session.scalars(
        select(ProjectDestination).where(ProjectDestination.project_id == project.id)
    ).all()
    destinations = [
        d for d in (session.get(Destination, r.destination_id) for r in rows) if d
    ]
    return SelectionOut(
        selected=[_describe(d, session) for d in destinations],
        project_state=project.state,
    )


# ---------------------------------------------------------------------------
# Researching a destination Preflight has never seen
# ---------------------------------------------------------------------------


class ResearchIn(BaseModel):
    #: What the person typed. "Sundance Film Festival", not a slug or a domain.
    query: str = Field(min_length=2, max_length=200)


class ResearchOut(BaseModel):
    id: uuid.UUID
    query: str
    state: str
    progress: str | None
    official_sources: int
    rejected_sources: int
    total_rules: int
    mandatory_rules: int
    failure_reason: str | None
    destination: DestinationOut | None


def _research_out(job, session: Session) -> ResearchOut:
    destination = None
    if job.destination_id is not None and job.state == "READY":
        row = session.get(Destination, job.destination_id)
        if row is not None:
            destination = _describe(row, session)
    return ResearchOut(
        id=job.id, query=job.query, state=job.state, progress=job.progress,
        official_sources=job.official_sources, rejected_sources=job.rejected_sources,
        total_rules=job.total_rules, mandatory_rules=job.mandatory_rules,
        failure_reason=job.failure_reason, destination=destination,
    )


@router.post("/destinations/research", response_model=ResearchOut, status_code=202)
def start_research(
    payload: ResearchIn,
    request: Request,
    user: User = Depends(current_user),
    session: Session = Depends(get_session),
) -> ResearchOut:
    """Find out what a destination currently publishes.

    Returns immediately with a row to watch. The work itself - searching,
    reading, extracting - takes minutes and happens off this request, because
    holding an HTTP connection open for that long is a promise about the
    network that nobody can keep.
    """
    job = DestinationResearch(
        requested_by=user.id, query=payload.query.strip(), state="QUEUED",
        progress="Starting",
    )
    session.add(job)
    session.commit()

    from ..core.db import session_factory
    from . import research as research_module

    research_module.start(job.id, session_factory(request))
    return _research_out(job, session)


@router.get("/destinations/research/{job_id}", response_model=ResearchOut)
def read_research(
    job_id: uuid.UUID,
    user: User = Depends(current_user),
    session: Session = Depends(get_session),
) -> ResearchOut:
    job = session.get(DestinationResearch, job_id)
    if job is None or job.requested_by != user.id:
        # Indistinguishable: someone else's research is not theirs to discover.
        raise HTTPException(status_code=404, detail="No such research")
    return _research_out(job, session)
