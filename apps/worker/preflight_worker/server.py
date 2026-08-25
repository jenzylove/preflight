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


class InspectAsset(BaseModel):
    storageKey: str  # noqa: N815 - matches the API's payload shape
    role: str


@app.post("/assets/inspect")
def inspect(payload: InspectAsset, response: Response) -> dict[str, object]:
    """Measure one stored asset and return the evidence.

    Measurement lives here rather than in the API because it requires opening
    the file, and the API deliberately carries no media toolchain. Keeping that
    boundary means a compromised API cannot read a customer's master; it can
    only ask this service to describe one.
    """
    import hashlib
    import tempfile

    from preflight_contracts import inspect_media

    from . import storage

    try:
        with tempfile.TemporaryDirectory(prefix="preflight-inspect-") as tmp:
            suffix = Path(payload.storageKey).suffix
            local = Path(tmp) / f"asset{suffix}"
            storage.download(payload.storageKey, local)

            digest = hashlib.sha256()
            with local.open("rb") as handle:
                for chunk in iter(lambda: handle.read(1024 * 1024), b""):
                    digest.update(chunk)

            if payload.role == "master":
                video = inspect_media.inspect_video(local)
                audio = inspect_media.inspect_audio(local)
                video.properties["videoStreamMd5"] = inspect_media.video_stream_md5(local)
                properties = {
                    "video": video.properties,
                    "audio": {
                        k: v for k, v in audio.properties.items()
                        if not k.startswith("_")
                    },
                }
                inspector, version = "ffprobe+ebur128", video.inspector_version
            elif payload.role == "subtitle":
                result = inspect_media.inspect_subtitle(local)
                properties, inspector, version = (
                    result.properties, result.inspector, result.inspector_version
                )
            else:
                result = inspect_media.inspect_poster(local)
                properties, inspector, version = (
                    result.properties, result.inspector, result.inspector_version
                )

            return {
                "sha256": digest.hexdigest(),
                "byteSize": local.stat().st_size,
                "properties": properties,
                "inspector": inspector,
                "inspectorVersion": version,
                "schemaVersion": inspect_media.INSPECTOR_SCHEMA_VERSION,
            }
    except inspect_media.InspectionError as exc:
        # A file that cannot be measured is rejected rather than guessed at.
        response.status_code = status.HTTP_422_UNPROCESSABLE_ENTITY
        return {"error": "unreadable", "detail": str(exc)[:300]}
    except storage.StorageError as exc:
        response.status_code = status.HTTP_409_CONFLICT
        return {"error": "missing", "detail": str(exc)[:300]}


__all__ = ["app", "run_job", "validate_package", "Path"]
