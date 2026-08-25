"""Asset upload and inspection.

Upload is two-phase on purpose. The client asks for an intent, uploads directly
to private storage with a scoped signed URL, then tells the API it finished — at
which point the server hashes and inspects the object it can actually see. The
server never takes the client's word for what was uploaded.
"""

from __future__ import annotations

import logging
import uuid

from fastapi import APIRouter, Depends, HTTPException, status
from preflight_contracts.state import ProjectState, transition_project
from pydantic import BaseModel, Field
from sqlalchemy import select
from sqlalchemy.orm import Session

from ..auth.identity import owned_project
from ..core.db import get_session
from ..core.models import Asset, AssetEvidence, Project
from . import storage

logger = logging.getLogger("preflight.assets")

router = APIRouter(prefix="/v1/projects/{project_id}/assets", tags=["assets"])

_EXTENSION_FOR = {
    "video/mp4": ".mp4",
    "video/quicktime": ".mov",
    "text/vtt": ".vtt",
    "application/x-subrip": ".srt",
    "text/plain": ".srt",
    "image/jpeg": ".jpg",
    "image/png": ".png",
}


class UploadIntent(BaseModel):
    role: str = Field(pattern=r"^(master|subtitle|poster)$")
    filename: str = Field(min_length=1, max_length=500)
    content_type: str = Field(max_length=120)
    byte_size: int = Field(gt=0)


class UploadIntentOut(BaseModel):
    asset_id: uuid.UUID
    upload_url: str
    expires_in_seconds: int


class AssetOut(BaseModel):
    id: uuid.UUID
    role: str
    original_filename: str
    content_type: str
    byte_size: int
    sha256: str | None
    custody_state: str
    immutable: bool
    measured_properties: dict | None = None
    inspector: str | None = None
    inspector_version: str | None = None


@router.post("/upload-intent", response_model=UploadIntentOut, status_code=201)
def create_upload_intent(
    payload: UploadIntent,
    project: Project = Depends(owned_project),
    session: Session = Depends(get_session),
) -> UploadIntentOut:
    try:
        storage.validate_upload(
            payload.role, payload.filename, payload.content_type, payload.byte_size
        )
    except storage.StorageError as exc:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(exc)) from exc

    asset_id = uuid.uuid4()
    extension = _EXTENSION_FOR.get(payload.content_type)
    if extension is None:
        raise HTTPException(status_code=400, detail="Unsupported content type")

    key = storage.storage_key(project.id, asset_id, payload.role, extension)

    asset = Asset(
        id=asset_id,
        project_id=project.id,
        role=payload.role,
        original_filename=payload.filename,
        storage_key=key,
        content_type=payload.content_type,
        byte_size=payload.byte_size,
        immutable=True,
        custody_state="AWAITING_UPLOAD",
    )
    session.add(asset)
    session.flush()

    try:
        url = storage.create_resumable_upload_url(
            key, payload.content_type, payload.byte_size
        )
    except storage.StorageError as exc:
        raise HTTPException(status_code=503, detail=str(exc)) from exc

    from ..core.config import get_settings

    return UploadIntentOut(
        asset_id=asset.id,
        upload_url=url,
        expires_in_seconds=get_settings().signed_url_ttl_seconds,
    )


@router.post("/{asset_id}/complete", response_model=AssetOut)
def complete_upload(
    asset_id: uuid.UUID,
    project: Project = Depends(owned_project),
    session: Session = Depends(get_session),
) -> AssetOut:
    """Confirm an upload by measuring what is actually in storage.

    The client reports only that it finished. Size, hash and every media
    property come from the object itself.
    """
    asset = session.scalar(
        select(Asset).where(Asset.id == asset_id, Asset.project_id == project.id)
    )
    if asset is None:
        raise HTTPException(status_code=404, detail="Not found")

    if asset.sha256 is not None:
        # Already completed. Idempotent by design: a retried completion must
        # not re-inspect or duplicate evidence.
        return _asset_out(asset, session)

    exists, actual_size = storage.object_exists(asset.storage_key)
    if not exists:
        raise HTTPException(status_code=409, detail="Upload has not arrived yet")

    if actual_size != asset.byte_size:
        asset.byte_size = actual_size

    evidence = _inspect_and_record(asset, session)

    asset.custody_state = "STORED"
    if project.state == ProjectState.DRAFT.value:
        project.state = transition_project(
            ProjectState.DRAFT, ProjectState.ASSETS_UPLOADED
        ).value

    session.flush()
    return _asset_out(asset, session, evidence)


def _inspect_and_record(asset: Asset, session: Session) -> AssetEvidence:
    """Ask the worker to measure the stored object, and record what it says.

    The API does not open the file. It carries no media toolchain by design, so
    a compromised API can ask for a description of a master but cannot read one.
    The worker is private and reachable only with a service identity token.
    """
    import google.auth.transport.requests
    import google.oauth2.id_token
    import httpx

    from ..core.config import get_settings

    settings = get_settings()
    base = settings.worker_base_url.rstrip("/")

    headers = {"Content-Type": "application/json"}
    try:
        auth_request = google.auth.transport.requests.Request()
        headers["Authorization"] = "Bearer " + google.oauth2.id_token.fetch_id_token(
            auth_request, base
        )
    except Exception:  # noqa: BLE001 - absent locally, present on Cloud Run
        logger.info("no service identity available; calling the worker unauthenticated")

    try:
        response = httpx.post(
            f"{base}/assets/inspect",
            json={"storageKey": asset.storage_key, "role": asset.role},
            headers=headers,
            timeout=300.0,
        )
    except httpx.HTTPError as exc:
        logger.warning("inspection service unreachable: %s", exc)
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="Measurement is temporarily unavailable. Your file was uploaded; "
                   "try completing it again shortly.",
        ) from None

    if response.status_code == 422:
        asset.custody_state = "REJECTED"
        detail = response.json().get("detail", "")
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail=f"This file could not be read as a valid {asset.role}: {detail}",
        )
    if response.status_code != 200:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="The uploaded file could not be measured.",
        )

    measured = response.json()
    asset.sha256 = measured["sha256"]
    if measured.get("byteSize"):
        asset.byte_size = measured["byteSize"]

    evidence = AssetEvidence(
        asset_id=asset.id,
        inspector=measured["inspector"],
        inspector_version=measured["inspectorVersion"],
        schema_version=measured["schemaVersion"],
        measured_properties_json=measured["properties"],
    )
    session.add(evidence)
    session.flush()
    return evidence


def _asset_out(
    asset: Asset, session: Session, evidence: AssetEvidence | None = None
) -> AssetOut:
    if evidence is None:
        evidence = session.scalar(
            select(AssetEvidence)
            .where(AssetEvidence.asset_id == asset.id)
            .order_by(AssetEvidence.created_at.desc())
        )
    return AssetOut(
        id=asset.id,
        role=asset.role,
        original_filename=asset.original_filename,
        content_type=asset.content_type,
        byte_size=asset.byte_size,
        sha256=asset.sha256,
        custody_state=asset.custody_state,
        immutable=asset.immutable,
        measured_properties=evidence.measured_properties_json if evidence else None,
        inspector=evidence.inspector if evidence else None,
        inspector_version=evidence.inspector_version if evidence else None,
    )


@router.get("", response_model=list[AssetOut])
def list_assets(
    project: Project = Depends(owned_project),
    session: Session = Depends(get_session),
) -> list[AssetOut]:
    assets = session.scalars(
        select(Asset)
        .where(Asset.project_id == project.id, Asset.deleted_at.is_(None))
        .order_by(Asset.created_at)
    ).all()
    return [_asset_out(a, session) for a in assets]
