"""Confirming or setting aside an extracted requirement.

Stage 3 of the product journey is the user confirming rules. This is that:
a producer looking at their own delivery can say a published requirement was
misread, and take responsibility for the judgement.

It is deliberately not a delete. The rule stays in the pack as context, the
decision is attributed and dated, and it appears in the passport as a stated
limitation. Whoever receives the package can see that a published requirement
was judged misextracted and by whom.
"""

from __future__ import annotations

import uuid
from datetime import datetime

from fastapi import APIRouter, Depends, HTTPException
from preflight_contracts.models import (
    Destination,
    Project,
    ProjectDestination,
    RuleDisposition,
    RulePackRow,
    RuleRow,
    SourceEvidenceRow,
    User,
)
from pydantic import BaseModel, Field
from sqlalchemy import select
from sqlalchemy.orm import Session

from ..auth.identity import current_user, owned_project
from ..core.db import get_session

router = APIRouter(prefix="/v1/projects/{project_id}", tags=["rules"])


class RuleOut(BaseModel):
    rule_id: uuid.UUID
    destination: str
    asset_type: str
    field: str
    operator: str
    expected: str | None
    severity: str
    confidence: str
    source_url: str | None
    source_excerpt: str | None
    disposition: str | None
    disposition_reason: str | None


@router.get("/rules", response_model=list[RuleOut])
def list_rules(
    project: Project = Depends(owned_project),
    session: Session = Depends(get_session),
) -> list[RuleOut]:
    """Every rule this project will be measured against, with its evidence."""
    selections = session.scalars(
        select(ProjectDestination).where(ProjectDestination.project_id == project.id)
    ).all()
    if not selections:
        return []

    dispositions = {
        d.rule_id: d for d in session.scalars(
            select(RuleDisposition).where(RuleDisposition.project_id == project.id)
        ).all()
    }

    out: list[RuleOut] = []
    for selection in selections:
        destination = session.get(Destination, selection.destination_id)
        pack = session.scalar(
            select(RulePackRow)
            .where(
                RulePackRow.destination_id == selection.destination_id,
                RulePackRow.status == "CONFIRMED",
            )
            .order_by(RulePackRow.version.desc())
        )
        if pack is None or destination is None:
            continue

        for row in session.scalars(
            select(RuleRow).where(RuleRow.rule_pack_id == pack.id)
        ).all():
            evidence = session.get(SourceEvidenceRow, row.source_evidence_id)
            decision = dispositions.get(row.id)
            out.append(RuleOut(
                rule_id=row.id,
                destination=destination.slug,
                asset_type=row.asset_type,
                field=row.field,
                operator=row.operator,
                expected=str(row.expected_value_json)
                if row.expected_value_json is not None else None,
                severity=row.severity,
                confidence=row.confidence,
                source_url=(evidence.url if evidence and not evidence.private else None),
                source_excerpt=(evidence.quoted_excerpt[:300] if evidence else None),
                disposition=decision.action if decision else None,
                disposition_reason=decision.reason if decision else None,
            ))
    return out


class DispositionIn(BaseModel):
    action: str = Field(pattern=r"^(accept|set_aside)$")
    reason: str = Field(min_length=8, max_length=1000)


class DispositionOut(BaseModel):
    rule_id: uuid.UUID
    action: str
    reason: str
    decided_at: datetime
    note: str


@router.put("/rules/{rule_id}/disposition", response_model=DispositionOut)
def set_disposition(
    rule_id: uuid.UUID,
    payload: DispositionIn,
    project: Project = Depends(owned_project),
    user: User = Depends(current_user),
    session: Session = Depends(get_session),
) -> DispositionOut:
    rule = session.get(RuleRow, rule_id)
    if rule is None:
        raise HTTPException(status_code=404, detail="Not found")

    # The rule must belong to a destination this project actually selected.
    pack = session.get(RulePackRow, rule.rule_pack_id)
    selected = session.scalar(
        select(ProjectDestination).where(
            ProjectDestination.project_id == project.id,
            ProjectDestination.destination_id == pack.destination_id,
        )
    ) if pack else None
    if selected is None:
        raise HTTPException(status_code=404, detail="Not found")

    existing = session.scalar(
        select(RuleDisposition).where(
            RuleDisposition.project_id == project.id,
            RuleDisposition.rule_id == rule_id,
        )
    )
    if existing is None:
        existing = RuleDisposition(
            project_id=project.id, rule_id=rule_id, decided_by=user.id,
            action=payload.action, reason=payload.reason.strip(),
        )
        session.add(existing)
    else:
        existing.action = payload.action
        existing.reason = payload.reason.strip()
        existing.decided_by = user.id
    session.flush()

    return DispositionOut(
        rule_id=rule_id,
        action=existing.action,
        reason=existing.reason,
        decided_at=existing.created_at,
        note=(
            "This requirement will not be measured against your files. It stays "
            "on record and appears in the release passport as a stated "
            "limitation."
            if payload.action == "set_aside"
            else "This requirement will be measured against your files."
        ),
    )
