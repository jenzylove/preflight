"""Delivery rooms.

A room is a read-only, expiring, revocable view of one verified package. It is
the only unauthenticated surface in the product, so it is the one written most
defensively:

  * A room can only be created for a package that is VERIFIED. There is no way
    to share something Preflight has not checked.
  * Every failure returns the same 404. Expired, revoked, wrong token and never
    existed are indistinguishable to a recipient, because telling them apart
    tells an attacker which tokens are real.
  * The response exposes an allowlist of fields. Bucket paths, project ids and
    owner details are not in it.
  * Downloads record that they happened. They do not record acceptance, which
    Preflight cannot observe.
"""

from __future__ import annotations

import logging
import uuid
from datetime import datetime

from fastapi import APIRouter, Depends, HTTPException, Response, status
from preflight_contracts.state import PackageState
from pydantic import BaseModel, Field
from sqlalchemy import select
from sqlalchemy.orm import Session

from ..assets import storage
from ..auth.identity import owned_project
from ..core.config import get_settings
from ..core.db import get_session
from ..core.models import DeliveryEvent, DeliveryRoom, Package, Project
from . import tokens

logger = logging.getLogger("preflight.delivery")

owner_router = APIRouter(prefix="/v1/projects/{project_id}", tags=["delivery"])
public_router = APIRouter(prefix="/v1/delivery", tags=["delivery"])

#: Recipients are never told which of these applied.
GONE = HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Not found")


class RoomCreate(BaseModel):
    recipient_label: str | None = Field(default=None, max_length=200)
    expires_in_hours: int | None = Field(default=None, ge=1, le=24 * 90)


class RoomOut(BaseModel):
    room_id: uuid.UUID
    url_token: str | None
    recipient_label: str | None
    expires_at: datetime
    revoked_at: datetime | None
    state: str
    note: str


@owner_router.post(
    "/packages/{package_id}/delivery-rooms", response_model=RoomOut, status_code=201
)
def create_room(
    package_id: uuid.UUID,
    payload: RoomCreate,
    project: Project = Depends(owned_project),
    session: Session = Depends(get_session),
) -> RoomOut:
    package = session.scalar(
        select(Package).where(
            Package.id == package_id, Package.project_id == project.id
        )
    )
    if package is None:
        raise GONE

    if package.state != PackageState.VERIFIED.value:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail=(
                "This package has not been verified. Preflight will not create a "
                "delivery link for a package it has not checked."
            ),
        )

    settings = get_settings()
    hours = payload.expires_in_hours or settings.delivery_token_ttl_hours
    token, token_hash = tokens.issue_token()

    room = DeliveryRoom(
        package_id=package.id,
        token_hash=token_hash,
        recipient_label=payload.recipient_label,
        expires_at=tokens.expiry_from_now(hours),
    )
    session.add(room)
    session.flush()

    return RoomOut(
        room_id=room.id,
        # Returned exactly once. It is not stored and cannot be shown again.
        url_token=token,
        recipient_label=room.recipient_label,
        expires_at=room.expires_at,
        revoked_at=None,
        state="active",
        note=(
            "Copy this link now — it is shown once and is not recoverable. "
            f"It stops working in {hours} hours, or immediately if you revoke it."
        ),
    )


@owner_router.get("/delivery-rooms", response_model=list[RoomOut])
def list_rooms(
    project: Project = Depends(owned_project),
    session: Session = Depends(get_session),
) -> list[RoomOut]:
    rooms = session.scalars(
        select(DeliveryRoom)
        .join(Package, Package.id == DeliveryRoom.package_id)
        .where(Package.project_id == project.id)
        .order_by(DeliveryRoom.created_at.desc())
    ).all()

    out = []
    for room in rooms:
        usable, state = tokens.is_usable(room.expires_at, room.revoked_at)
        out.append(RoomOut(
            room_id=room.id,
            url_token=None,   # never recoverable after creation
            recipient_label=room.recipient_label,
            expires_at=room.expires_at,
            revoked_at=room.revoked_at,
            state=state,
            note="" if usable else f"This link is {state} and no longer works.",
        ))
    return out


@owner_router.delete("/delivery-rooms/{room_id}", status_code=200)
def revoke_room(
    room_id: uuid.UUID,
    project: Project = Depends(owned_project),
    session: Session = Depends(get_session),
) -> dict[str, str]:
    """Revocation takes effect immediately and is idempotent."""
    room = session.scalar(
        select(DeliveryRoom)
        .join(Package, Package.id == DeliveryRoom.package_id)
        .where(DeliveryRoom.id == room_id, Package.project_id == project.id)
    )
    if room is None:
        raise GONE

    if room.revoked_at is None:
        room.revoked_at = datetime.now(tz=None)
        session.flush()

    return {"state": "revoked", "note": "This link no longer works."}


# ---------------------------------------------------------------------------
# Public surface
# ---------------------------------------------------------------------------

class PublicRoomOut(BaseModel):
    """Deliberately narrow. Everything a recipient needs, nothing more."""

    project_title: str
    destination: str
    verified: bool
    package_sha256: str | None
    file_count: int
    expires_at: datetime
    limitations: list[str]


def _load_room(token: str, session: Session) -> tuple[DeliveryRoom, Package]:
    """Resolve a token to a room, or raise the same 404 for every failure."""
    room = session.scalar(
        select(DeliveryRoom).where(DeliveryRoom.token_hash == tokens.hash_token(token))
    )
    if room is None:
        logger.info("delivery lookup failed: no such token")
        raise GONE

    usable, state = tokens.is_usable(room.expires_at, room.revoked_at)
    if not usable:
        logger.info("delivery lookup refused: room %s is %s", room.id, state)
        _record(session, room, "DENIED", {"reason": state})
        raise GONE

    package = session.get(Package, room.package_id)
    if package is None or package.state != PackageState.VERIFIED.value:
        raise GONE

    return room, package


def _record(session: Session, room: DeliveryRoom, event: str, safe: dict) -> None:
    """Record what happened, with nothing identifying in it.

    No IP, no user agent, no filename. The owner needs to know a download
    occurred, not to be handed a surveillance log about their recipient.
    """
    session.add(DeliveryEvent(
        delivery_room_id=room.id, event_type=event, safe_metadata_json=safe
    ))
    session.flush()


@public_router.get("/{token}", response_model=PublicRoomOut)
def open_room(
    token: str,
    response: Response,
    session: Session = Depends(get_session),
) -> PublicRoomOut:
    response.headers["Cache-Control"] = "no-store"
    response.headers["X-Robots-Tag"] = "noindex, nofollow"

    room, package = _load_room(token, session)
    project = session.get(Project, package.project_id)
    manifest = package.manifest_json or {}

    _record(session, room, "OPENED", {})

    return PublicRoomOut(
        project_title=project.title if project else "",
        destination=manifest.get("destinationId", ""),
        verified=True,
        package_sha256=package.sha256,
        file_count=len(manifest.get("files", [])),
        expires_at=room.expires_at,
        limitations=manifest.get("limitations", []),
    )


class DownloadOut(BaseModel):
    url: str
    expires_in_seconds: int
    sha256: str | None
    note: str


@public_router.post("/{token}/download-intent", response_model=DownloadOut)
def download(
    token: str,
    response: Response,
    session: Session = Depends(get_session),
) -> DownloadOut:
    """Issue a short-lived signed URL for the package.

    The bucket path never reaches the recipient; they receive a signed URL that
    expires quickly and cannot be used to reach anything else.
    """
    response.headers["Cache-Control"] = "no-store"

    room, package = _load_room(token, session)
    if not package.storage_key:
        raise GONE

    settings = get_settings()
    try:
        url = storage.create_download_url(
            package.storage_key, f"{room.recipient_label or 'package'}.zip"
        )
    except storage.StorageError:
        logger.exception("could not sign a download for room %s", room.id)
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="This download is temporarily unavailable. Please try again.",
        ) from None

    _record(session, room, "DOWNLOAD_STARTED", {})

    return DownloadOut(
        url=url,
        expires_in_seconds=settings.signed_url_ttl_seconds,
        sha256=package.sha256,
        note=(
            "Check this hash against the file you receive to confirm it arrived "
            "intact."
        ),
    )
