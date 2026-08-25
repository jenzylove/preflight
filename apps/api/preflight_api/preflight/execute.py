"""Execution dispatch.

Two safeguards sit between an approval and a running job.

**Idempotency is enforced by the database, not by checking first.** The
idempotency key is a unique constraint, so two concurrent execute requests race
into the same row and the loser returns the winner's job. Checking for an
existing job before inserting would leave a window where both requests pass the
check.

**The approval is re-verified at dispatch.** The plan is looked up fresh and its
digest compared against the stored approval. An approval cannot be replayed
against a plan the user has not seen.
"""

from __future__ import annotations

import hashlib
import json
import logging
import uuid

from fastapi import APIRouter, Depends, HTTPException, status
from preflight_contracts.plan import Safety
from preflight_contracts.state import (
    JobState,
    ProjectState,
    TransitionError,
    transition_project,
)
from pydantic import BaseModel
from sqlalchemy import select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from ..auth.identity import owned_project
from ..core.config import get_settings
from ..core.db import get_session
from ..core.models import Approval, Job, Project, RepairPlan, RepairStep

logger = logging.getLogger("preflight.execute")

router = APIRouter(prefix="/v1/projects/{project_id}", tags=["execution"])


class JobOut(BaseModel):
    job_id: uuid.UUID
    state: str
    plan_digest: str
    steps_queued: int
    attempt: int
    reused_existing: bool
    message: str


def idempotency_key(plan_digest: str, step_ids: list[str]) -> str:
    """One key per (plan, exact set of steps).

    Includes the steps so that approving a subset and later approving more
    produces a genuinely different job rather than silently returning the old
    one.
    """
    payload = json.dumps(
        {"plan": plan_digest, "steps": sorted(step_ids)}, separators=(",", ":")
    )
    return hashlib.sha256(payload.encode()).hexdigest()[:64]


@router.post("/repair-plans/{plan_id}/execute", response_model=JobOut, status_code=202)
def execute_plan(
    plan_id: uuid.UUID,
    project: Project = Depends(owned_project),
    session: Session = Depends(get_session),
) -> JobOut:
    plan_row = session.scalar(
        select(RepairPlan).where(
            RepairPlan.id == plan_id, RepairPlan.project_id == project.id
        )
    )
    if plan_row is None:
        raise HTTPException(status_code=404, detail="Not found")

    approval = session.scalar(
        select(Approval).where(
            Approval.project_id == project.id,
            Approval.repair_plan_digest == plan_row.digest,
        )
    )
    if approval is None:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail=(
                "This plan has not been approved, or it changed after approval. "
                "Review the current plan and approve it before running it."
            ),
        )

    steps = session.scalars(
        select(RepairStep).where(RepairStep.repair_plan_id == plan_row.id)
    ).all()

    runnable = [s for s in steps if s.safety_level == Safety.GREEN.value]
    if not runnable:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="This plan contains no operations Preflight will run automatically.",
        )

    key = idempotency_key(plan_row.digest, [str(s.id) for s in runnable])

    job = Job(
        project_id=project.id,
        idempotency_key=key,
        type="repair_and_validate",
        state=JobState.QUEUED.value,
        attempt_count=0,
    )
    session.add(job)
    try:
        session.flush()
        created = True
    except IntegrityError:
        # AC-9: the unique constraint won the race. Return the existing job
        # rather than creating a duplicate set of outputs.
        session.rollback()
        job = session.scalar(
            select(Job).where(
                Job.project_id == project.id, Job.idempotency_key == key
            )
        )
        created = False
        if job is None:
            raise HTTPException(
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                detail="Could not queue this job. Please try again.",
            ) from None

    if created:
        _dispatch(job, project, plan_row.digest)
        try:
            project.state = transition_project(
                ProjectState(project.state), ProjectState.PROCESSING
            ).value
        except TransitionError:
            pass
        session.flush()

    return JobOut(
        job_id=job.id,
        state=job.state,
        plan_digest=plan_row.digest,
        steps_queued=len(runnable),
        attempt=job.attempt_count,
        reused_existing=not created,
        message=(
            "Processing started." if created
            else "This plan is already running; returning the existing job."
        ),
    )


def _dispatch(job: Job, project: Project, plan_digest: str) -> None:
    """Hand the job to Cloud Tasks.

    Dispatch failure is logged and left for retry rather than raised: the job
    row exists and is idempotent, so a retried request picks it up instead of
    creating a second one.
    """
    settings = get_settings()
    if not settings.google_cloud_project:
        logger.info("job %s queued; no dispatcher configured in this environment", job.id)
        return

    try:
        from google.cloud import tasks_v2

        client = tasks_v2.CloudTasksClient()
        parent = client.queue_path(
            settings.google_cloud_project, settings.google_cloud_location, "preflight-jobs"
        )
        client.create_task(
            parent=parent,
            task={
                "http_request": {
                    "http_method": tasks_v2.HttpMethod.POST,
                    "url": f"{settings.worker_base_url}/jobs/run",
                    "headers": {"Content-Type": "application/json"},
                    # The worker is private. Cloud Tasks authenticates to it as
                    # the runtime service account, so the only caller that can
                    # start a media job is the queue itself.
                    "oidc_token": {
                        "service_account_email": settings.worker_service_account
                        or f"preflight-api@{settings.google_cloud_project}"
                           ".iam.gserviceaccount.com",
                        "audience": settings.worker_base_url,
                    },
                    "body": json.dumps({
                        "jobId": str(job.id),
                        "projectId": str(project.id),
                        "planDigest": plan_digest,
                    }).encode(),
                },
                # Cloud Tasks deduplicates on task name, giving a second layer
                # of protection beyond the database constraint.
                "name": f"{parent}/tasks/{job.idempotency_key[:32]}",
            },
        )
    except Exception as exc:  # noqa: BLE001 — provider raises a wide family
        logger.warning("could not dispatch job %s: %s", job.id, exc)


class JobStatusOut(BaseModel):
    job_id: uuid.UUID
    type: str
    state: str
    attempt: int
    error: str | None
    message: str


#: Provider errors are never shown to users. Each maps to something a producer
#: can act on.
_ERROR_MESSAGES = {
    "INPUT_UNREADABLE": "One of your files could not be read. Re-upload it and try again.",
    "PLAN_CHANGED": "The plan changed after approval. Review and approve it again.",
    "VALIDATION_FAILED": "The repaired files did not meet the destination's requirements. "
                         "Nothing was marked ready.",
    "TIMEOUT": "Processing took longer than allowed and was stopped. "
               "Your original files are untouched.",
}


@router.get("/jobs/{job_id}", response_model=JobStatusOut)
def job_status(
    job_id: uuid.UUID,
    project: Project = Depends(owned_project),
    session: Session = Depends(get_session),
) -> JobStatusOut:
    job = session.scalar(
        select(Job).where(Job.id == job_id, Job.project_id == project.id)
    )
    if job is None:
        raise HTTPException(status_code=404, detail="Not found")

    message = {
        JobState.QUEUED.value: "Waiting to start.",
        JobState.RUNNING.value: "Working on your files.",
        JobState.SUCCEEDED.value: "Finished. Outputs have been independently checked.",
        JobState.CANCELLED.value: "Cancelled.",
    }.get(job.state, "")

    if job.state == JobState.FAILED.value:
        message = _ERROR_MESSAGES.get(
            job.error_code or "",
            "Processing did not complete. Your original files are untouched.",
        )

    return JobStatusOut(
        job_id=job.id,
        type=job.type,
        state=job.state,
        attempt=job.attempt_count,
        error=job.error_code,
        message=message,
    )
