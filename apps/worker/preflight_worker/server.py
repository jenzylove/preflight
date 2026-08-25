"""Worker HTTP surface.

Cloud Tasks delivers jobs here. The endpoint is deliberately thin: it fetches
inputs, runs the approved plan, validates the outputs and reports. It holds no
opinion about whether the result is good — that is the validator's decision,
derived from measurements.

Cloud Tasks retries on non-2xx, so the response code is a real signal:
  200  the job reached a conclusion, good or bad — do not retry
  500  something transient went wrong — retry is appropriate
"""

from __future__ import annotations

import logging
from pathlib import Path

from fastapi import FastAPI, Response, status
from pydantic import BaseModel

from .executor import ExecutionRefused, run_job
from .jobs import JobRefused
from .validate import VALIDATOR_VERSION, validate_package

logger = logging.getLogger("preflight.worker.server")
logging.basicConfig(level=logging.INFO)

app = FastAPI(title="Preflight worker", version="0.1.0")


class RunJob(BaseModel):
    jobId: str  # noqa: N815 - Cloud Tasks payload shape
    projectId: str  # noqa: N815
    planDigest: str  # noqa: N815


@app.get("/health/live")
def live() -> dict[str, str]:
    return {"status": "alive", "validator": VALIDATOR_VERSION}


@app.post("/jobs/run")
def run(payload: RunJob, response: Response) -> dict[str, object]:
    """Execute one approved plan and validate what it produced.

    The work itself is done by executor.run_job and validate_package; this
    function's only judgement is which failures deserve a retry.
    """
    logger.info("job %s starting for plan %s", payload.jobId, payload.planDigest[:16])

    try:
        outcome = _process(payload)
    except (ExecutionRefused, JobRefused) as exc:
        # A refusal is a decision, not a fault. Retrying would refuse again.
        logger.warning("job %s refused: %s", payload.jobId, exc)
        return {"jobId": payload.jobId, "state": "REFUSED", "reason": str(exc)}
    except Exception:
        logger.exception("job %s hit an unexpected error", payload.jobId)
        response.status_code = status.HTTP_500_INTERNAL_SERVER_ERROR
        return {"jobId": payload.jobId, "state": "RETRY"}

    return outcome


def _process(payload: RunJob) -> dict[str, object]:
    """Run the job against real storage and a real database."""
    import os
    import uuid as _uuid

    from sqlalchemy import create_engine
    from sqlalchemy.orm import Session

    from .jobs import process_job

    database_url = os.environ.get("DATABASE_URL", "")
    if not database_url:
        raise RuntimeError("DATABASE_URL is not configured")

    engine = create_engine(database_url, pool_pre_ping=True, pool_size=2)
    try:
        with Session(engine) as session:
            outcome = process_job(_uuid.UUID(payload.jobId), session)
            session.commit()
    finally:
        engine.dispose()

    return {"jobId": payload.jobId, "validator": VALIDATOR_VERSION, **outcome}


__all__ = ["app", "run_job", "validate_package", "Path"]
