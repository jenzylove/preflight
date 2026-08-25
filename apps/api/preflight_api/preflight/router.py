"""Preflight runs, repair plans and approval.

The approval endpoint is the one that matters. It stores a digest, not a
sentiment. Execution later recomputes the plan from current state and refuses
unless the digest still matches — so an approval cannot be replayed against a
plan the user never saw.
"""

from __future__ import annotations

import uuid
from datetime import datetime
from typing import Any

from fastapi import APIRouter, Depends, HTTPException, status
from preflight_contracts.compare import (
    Assertion as ContractAssertion,
)
from preflight_contracts.compare import (
    Result,
    comparison_digest,
    evaluate_pack,
    find_conflicts,
    is_ready,
)
from preflight_contracts.plan import OPERATION_CATALOGUE, Plan, build_plan
from preflight_contracts.rules import AssetType, Severity
from preflight_contracts.state import ProjectState, TransitionError, transition_project
from pydantic import BaseModel, Field
from sqlalchemy import select
from sqlalchemy.orm import Session

from ..auth.identity import current_user, owned_project
from ..core.db import get_session
from ..core.models import (
    Approval,
    Asset,
    AssetEvidence,
    Project,
    RepairPlan,
    RepairStep,
    User,
)
from .rulepacks import load_project_rule_packs

router = APIRouter(prefix="/v1/projects/{project_id}", tags=["preflight"])


# ---------------------------------------------------------------------------
# Response shapes
# ---------------------------------------------------------------------------

class AssertionOut(BaseModel):
    rule_id: str
    destination_id: str
    asset_type: str
    field: str
    published: str
    measured: Any
    result: str
    severity: str
    source_url: str | None
    source_excerpt: str | None
    repair_operation: str | None
    explanation: str


class DestinationMatrix(BaseModel):
    destination_id: str
    rule_pack_digest: str
    satisfied: int
    total: int
    ready: bool
    blocking: list[str]
    assertions: list[AssertionOut]


class StepOut(BaseModel):
    step_id: str
    operation: str
    safety: str
    what_it_does: str
    input_asset: str
    output: str
    parameters: dict[str, Any]
    resolves: list[str]
    depends_on: list[str]
    executable: bool


class PlanOut(BaseModel):
    plan_id: uuid.UUID | None = None
    digest: str
    steps: list[StepOut]
    needs_your_decision: list[StepOut]
    blocked: list[dict[str, Any]]
    unresolved: list[dict[str, Any]]
    preserved_assets: list[str]
    estimated_seconds: int
    shared_across_destinations: dict[str, list[str]]


class PreflightOut(BaseModel):
    run_id: uuid.UUID
    comparison_digest: str
    destinations: list[DestinationMatrix]
    conflicts: list[dict[str, Any]]
    plan: PlanOut
    limitations: list[str]


# ---------------------------------------------------------------------------
# Measurement assembly
# ---------------------------------------------------------------------------

def _measured_properties(project_id: uuid.UUID, session: Session) -> dict[AssetType, dict]:
    """Collect the latest measurement for each asset role.

    Every value here came from a tool. Nothing is defaulted or inferred — an
    absent property stays absent so the engine reports NOT_MEASURED rather
    than silently passing.
    """
    rows = session.execute(
        select(Asset, AssetEvidence)
        .join(AssetEvidence, AssetEvidence.asset_id == Asset.id)
        .where(Asset.project_id == project_id, Asset.deleted_at.is_(None))
        .order_by(AssetEvidence.created_at)
    ).all()

    measured: dict[AssetType, dict] = {}
    for asset, evidence in rows:
        properties = evidence.measured_properties_json or {}
        if asset.role == "master":
            measured[AssetType.VIDEO] = properties.get("video", {})
            measured[AssetType.AUDIO] = properties.get("audio", {})
        elif asset.role == "subtitle":
            measured[AssetType.SUBTITLE] = properties
        elif asset.role == "poster":
            measured[AssetType.POSTER] = properties
    return measured


def _to_out(assertion: ContractAssertion, evidence_lookup: dict) -> AssertionOut:
    source = evidence_lookup.get(assertion.source_evidence_id)
    return AssertionOut(
        rule_id=assertion.rule_id,
        destination_id=assertion.destination_id,
        asset_type=assertion.asset_type.value,
        field=assertion.field_name,
        published=assertion.expected,
        measured=assertion.measured,
        result=assertion.result.value,
        severity=assertion.severity.value,
        source_url=getattr(source, "url", None),
        source_excerpt=getattr(source, "quoted_excerpt", None),
        repair_operation=assertion.repair_operation,
        explanation=assertion.explanation,
    )


def _step_out(step, executable: bool) -> StepOut:
    return StepOut(
        step_id=step.step_id,
        operation=step.operation,
        safety=step.safety.value,
        what_it_does=OPERATION_CATALOGUE[step.operation]["explains"],
        input_asset=step.input_role,
        output=step.output_role,
        parameters=step.parameters,
        resolves=list(step.resolves),
        depends_on=list(step.depends_on),
        executable=executable,
    )


def _plan_out(
    plan: Plan, runtime_seconds: int, roles: set[str],
    plan_row=None, session=None,
) -> PlanOut:
    # Map each planned step onto the row that was persisted for it, so the
    # step_id the user approves is the one the worker will look up.
    row_for: dict[str, str] = {}
    if plan_row is not None and session is not None:
        rows = session.scalars(
            select(RepairStep).where(RepairStep.repair_plan_id == plan_row.id)
        ).all()
        used: set[str] = set()
        for step in plan.steps:
            match = next(
                (r for r in rows
                 if r.operation == step.operation
                 and r.output_role == step.output_role
                 and str(r.id) not in used),
                None,
            )
            if match is not None:
                row_for[step.step_id] = str(match.id)
                used.add(str(match.id))

    def out(step, executable: bool) -> StepOut:
        rendered = _step_out(step, executable)
        rendered.step_id = row_for.get(step.step_id, rendered.step_id)
        return rendered

    return PlanOut(
        plan_id=plan_row.id if plan_row is not None else None,
        digest=plan.digest(),
        steps=[out(s, True) for s in plan.green],
        needs_your_decision=[out(s, False) for s in plan.needs_decision],
        blocked=plan.blocked,
        unresolved=plan.unresolved,
        preserved_assets=plan.preserved_assets(roles),
        estimated_seconds=plan.estimated_seconds(runtime_seconds),
        shared_across_destinations=plan.reused,
    )


# ---------------------------------------------------------------------------
# Endpoints
# ---------------------------------------------------------------------------

@router.post("/preflight", response_model=PreflightOut, status_code=201)
def run_preflight(
    project: Project = Depends(owned_project),
    session: Session = Depends(get_session),
) -> PreflightOut:
    """Compare measured assets against confirmed rule packs.

    Deterministic throughout: no model participates, and equivalent inputs
    produce an identical comparison digest.
    """
    packs, evidence_lookup, ambiguous_ids = load_project_rule_packs(project.id, session)
    if not packs:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="Confirm at least one destination's requirements before running preflight",
        )

    measured = _measured_properties(project.id, session)
    if not measured:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="Upload and complete at least one asset before running preflight",
        )

    from ..core.models import PreflightRun

    matrices: list[DestinationMatrix] = []
    all_assertions: list[ContractAssertion] = []
    by_destination: dict[str, list[ContractAssertion]] = {}
    loudness_targets: dict[str, tuple[float, float]] = {}

    for pack in packs:
        assertions = evaluate_pack(pack, measured, frozenset(ambiguous_ids))
        by_destination[pack.destination_id] = assertions
        all_assertions.extend(assertions)

        for rule in pack.rules:
            if (rule.asset_type is AssetType.AUDIO
                    and rule.field_name == "integratedLoudnessLufs"
                    and isinstance(rule.value, list) and len(rule.value) == 2):
                loudness_targets[pack.destination_id] = (rule.value[0], rule.value[1])

        considered = [a for a in assertions if a.result is not Result.NOT_APPLICABLE]
        satisfied = [a for a in considered if a.result is Result.PASS]
        blocking = [
            f"{a.asset_type.value}.{a.field_name}"
            for a in considered
            if a.severity is Severity.REQUIRED and a.result is not Result.PASS
        ]
        matrices.append(DestinationMatrix(
            destination_id=pack.destination_id,
            rule_pack_digest=pack.digest(),
            satisfied=len(satisfied),
            total=len(considered),
            ready=is_ready(considered),
            blocking=blocking,
            assertions=[_to_out(a, evidence_lookup) for a in considered],
        ))

    plan = build_plan(by_destination, loudness_targets=loudness_targets)
    roles = {
        row[0] for row in session.execute(
            select(Asset.role).where(
                Asset.project_id == project.id, Asset.deleted_at.is_(None)
            )
        ).all()
    }

    run = PreflightRun(
        project_id=project.id,
        rule_pack_set_digest=_pack_set_digest(packs),
        comparison_digest=comparison_digest(all_assertions),
        state="COMPLETE",
        completed_at=datetime.now(tz=None),
    )
    session.add(run)
    session.flush()

    plan_row = _persist_plan(project, run, plan, session)

    try:
        project.state = transition_project(
            ProjectState(project.state), ProjectState.PREFLIGHT_COMPLETE
        ).value
    except TransitionError:
        pass  # already past this point; re-running preflight is allowed

    return PreflightOut(
        run_id=run.id,
        comparison_digest=run.comparison_digest,
        destinations=matrices,
        conflicts=find_conflicts(packs),
        plan=_plan_out(plan, project.runtime_seconds or 60, roles, plan_row, session),
        limitations=_limitations(plan, matrices),
    )


def _pack_set_digest(packs) -> str:
    import hashlib
    joined = "|".join(sorted(f"{p.destination_id}:{p.digest()}" for p in packs))
    return hashlib.sha256(joined.encode()).hexdigest()[:32]


def _limitations(plan: Plan, matrices: list[DestinationMatrix]) -> list[str]:
    """What Preflight could not settle. Shown everywhere, including the passport.

    A verified package that hides its limitations is worse than an unverified
    one, because the user stops looking.
    """
    notes: list[str] = []
    if plan.unresolved:
        notes.append(
            f"{len(plan.unresolved)} requirement(s) could not be resolved automatically "
            f"and need your confirmation."
        )
    if plan.blocked:
        notes.append(
            f"{len(plan.blocked)} requirement(s) need professional work Preflight "
            f"does not perform."
        )
    if plan.needs_decision:
        notes.append(
            f"{len(plan.needs_decision)} repair(s) would change the picture or audio "
            f"and will not run without a separate decision from you."
        )
    notes.append(
        "Preflight verifies against published requirements as retrieved. It cannot "
        "guarantee that any destination will accept a delivery."
    )
    return notes


def _persist_plan(project: Project, run, plan: Plan, session: Session) -> RepairPlan:
    digest = plan.digest()
    existing = session.scalar(
        select(RepairPlan).where(
            RepairPlan.project_id == project.id, RepairPlan.digest == digest
        )
    )
    if existing is not None:
        return existing

    row = RepairPlan(
        project_id=project.id,
        preflight_run_id=run.id,
        digest=digest,
        state="DRAFT",
        estimated_seconds=plan.estimated_seconds(project.runtime_seconds or 60),
    )
    session.add(row)
    session.flush()

    for step in plan.steps:
        session.add(RepairStep(
            repair_plan_id=row.id,
            operation=step.operation,
            safety_level=step.safety.value,
            output_role=step.output_role,
            parameters_json=step.parameters,
            dependency_ids_json=list(step.depends_on),
            state="PLANNED",
        ))
    session.flush()
    return row


class ApprovalIn(BaseModel):
    plan_digest: str = Field(min_length=8, max_length=64)
    approved_step_ids: list[str] = Field(min_length=1)


class ApprovalOut(BaseModel):
    approved_at: datetime
    plan_digest: str
    approved_steps: list[str]
    note: str


@router.post("/repair-plans/{plan_id}/approve", response_model=ApprovalOut, status_code=201)
def approve_plan(
    plan_id: uuid.UUID,
    payload: ApprovalIn,
    project: Project = Depends(owned_project),
    user: User = Depends(current_user),
    session: Session = Depends(get_session),
) -> ApprovalOut:
    """Bind consent to one exact plan.

    The digest the client sends must match the plan it is approving. A mismatch
    means the user is looking at a stale plan, and approving it would consent to
    work they have not seen.
    """
    plan_row = session.scalar(
        select(RepairPlan).where(
            RepairPlan.id == plan_id, RepairPlan.project_id == project.id
        )
    )
    if plan_row is None:
        raise HTTPException(status_code=404, detail="Not found")

    if payload.plan_digest != plan_row.digest:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail=(
                "This plan has changed since you reviewed it. "
                "Re-run preflight and review the current plan before approving."
            ),
        )

    # Approving a plan never authorises the operations Preflight refuses to
    # automate. The worker filters to green steps regardless of what is listed
    # here, so a yellow id in the payload grants nothing.

    existing = session.scalar(
        select(Approval).where(
            Approval.project_id == project.id,
            Approval.repair_plan_digest == plan_row.digest,
        )
    )
    if existing is not None:
        return ApprovalOut(
            approved_at=existing.created_at,
            plan_digest=existing.repair_plan_digest,
            approved_steps=existing.approved_step_ids_json,
            note="This plan was already approved.",
        )

    approval = Approval(
        project_id=project.id,
        owner_id=user.id,
        repair_plan_digest=plan_row.digest,
        approved_step_ids_json=payload.approved_step_ids,
    )
    session.add(approval)
    plan_row.state = "APPROVED"

    try:
        project.state = transition_project(
            ProjectState(project.state), ProjectState.REPAIR_APPROVED
        ).value
    except TransitionError as exc:
        raise HTTPException(status_code=409, detail=str(exc)) from exc

    session.flush()
    return ApprovalOut(
        approved_at=approval.created_at,
        plan_digest=approval.repair_plan_digest,
        approved_steps=payload.approved_step_ids,
        note=(
            "Only the green operations in this plan will run. Anything that "
            "would change the picture or audio needs a separate decision."
        ),
    )


@router.get("/preflight/latest", response_model=PreflightOut)
def latest_preflight(
    project: Project = Depends(owned_project),
    session: Session = Depends(get_session),
) -> PreflightOut:
    """Re-derive the most recent preflight result.

    Recomputed from the stored rule packs and stored measurements rather than
    from a cached payload, so what the page shows is always what the engine
    currently concludes from the evidence on record. A stale cached matrix
    would be a claim nobody could check.
    """
    from ..core.models import PreflightRun

    previous = session.scalar(
        select(PreflightRun)
        .where(PreflightRun.project_id == project.id)
        .order_by(PreflightRun.created_at.desc())
    )
    if previous is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="No preflight has been run for this project yet.",
        )
    return run_preflight(project=project, session=session)
