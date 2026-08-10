"""Project lifecycle.

Note what the request models do not contain: an owner id. There is no field to
send one in, so there is no way to get it wrong.
"""

from __future__ import annotations

import uuid
from datetime import datetime

from fastapi import APIRouter, Depends, HTTPException, status
from preflight_contracts.state import ProjectState, TransitionError, transition_project
from pydantic import BaseModel, Field
from sqlalchemy import func, select
from sqlalchemy.orm import Session

from ..auth.identity import current_user, owned_project
from ..core.db import get_session, owned_projects
from ..core.models import Asset, DeletionRequest, Project, User

router = APIRouter(prefix="/v1/projects", tags=["projects"])


class ProjectCreate(BaseModel):
    title: str = Field(min_length=1, max_length=300)
    project_type: str = Field(pattern=r"^(feature|short|documentary|trailer|series|other)$")
    primary_language: str | None = Field(default=None, max_length=20)
    runtime_seconds: int | None = Field(default=None, ge=0, le=60 * 60 * 12)
    country_of_origin: str | None = Field(default=None, min_length=2, max_length=2)
    internal_code: str | None = Field(default=None, max_length=100)


class ProjectOut(BaseModel):
    id: uuid.UUID
    title: str
    project_type: str
    primary_language: str | None
    runtime_seconds: int | None
    country_of_origin: str | None
    state: str
    created_at: datetime

    @classmethod
    def of(cls, project: Project) -> ProjectOut:
        return cls(
            id=project.id,
            title=project.title,
            project_type=project.project_type,
            primary_language=project.primary_language,
            runtime_seconds=project.runtime_seconds,
            country_of_origin=project.country_of_origin,
            state=project.state,
            created_at=project.created_at,
        )


@router.post("", response_model=ProjectOut, status_code=status.HTTP_201_CREATED)
def create_project(
    payload: ProjectCreate,
    user: User = Depends(current_user),
    session: Session = Depends(get_session),
) -> ProjectOut:
    project = Project(
        owner_id=user.id,
        title=payload.title,
        project_type=payload.project_type,
        primary_language=payload.primary_language,
        runtime_seconds=payload.runtime_seconds,
        country_of_origin=payload.country_of_origin,
        internal_code=payload.internal_code,
        state=ProjectState.DRAFT.value,
    )
    session.add(project)
    session.flush()
    return ProjectOut.of(project)


@router.get("", response_model=list[ProjectOut])
def list_projects(
    user: User = Depends(current_user),
    session: Session = Depends(get_session),
) -> list[ProjectOut]:
    projects = session.scalars(
        owned_projects(user.id).order_by(Project.created_at.desc())
    ).all()
    return [ProjectOut.of(p) for p in projects]


@router.get("/{project_id}", response_model=ProjectOut)
def get_project(project: Project = Depends(owned_project)) -> ProjectOut:
    return ProjectOut.of(project)


class DeletionOut(BaseModel):
    state: str
    objects_total: int
    objects_deleted: int
    requested_at: datetime


@router.delete("/{project_id}", response_model=DeletionOut, status_code=status.HTTP_202_ACCEPTED)
def delete_project(
    project: Project = Depends(owned_project),
    user: User = Depends(current_user),
    session: Session = Depends(get_session),
) -> DeletionOut:
    """Request deletion. Asynchronous, auditable, and honest about progress.

    The project moves to DELETION_PENDING immediately so nothing further can be
    built from it, but the objects themselves are removed by a worker. Reporting
    'deleted' before the bytes are gone would be a lie about the one thing users
    most need to trust.
    """
    existing = session.scalar(
        select(DeletionRequest).where(
            DeletionRequest.project_id == project.id,
            DeletionRequest.state.in_(("PENDING", "RUNNING")),
        )
    )
    if existing is not None:
        return DeletionOut(
            state=existing.state,
            objects_total=existing.objects_total,
            objects_deleted=existing.objects_deleted,
            requested_at=existing.requested_at,
        )

    try:
        project.state = transition_project(
            ProjectState(project.state), ProjectState.DELETION_PENDING
        ).value
    except TransitionError as exc:
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail=str(exc)) from exc

    pending_objects = session.scalar(
        select(func.count())
        .select_from(Asset)
        .where(Asset.project_id == project.id, Asset.deleted_at.is_(None))
    ) or 0

    request = DeletionRequest(
        project_id=project.id,
        requested_by=user.id,
        state="PENDING",
        objects_total=pending_objects,
        objects_deleted=0,
    )
    session.add(request)
    session.flush()

    return DeletionOut(
        state=request.state,
        objects_total=request.objects_total,
        objects_deleted=request.objects_deleted,
        requested_at=request.requested_at,
    )


@router.get("/{project_id}/deletion", response_model=DeletionOut)
def deletion_status(
    project: Project = Depends(owned_project),
    session: Session = Depends(get_session),
) -> DeletionOut:
    request = session.scalar(
        select(DeletionRequest)
        .where(DeletionRequest.project_id == project.id)
        .order_by(DeletionRequest.requested_at.desc())
    )
    if request is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Not found")
    return DeletionOut(
        state=request.state,
        objects_total=request.objects_total,
        objects_deleted=request.objects_deleted,
        requested_at=request.requested_at,
    )
