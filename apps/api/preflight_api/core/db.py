"""Database session management.

``owned_query`` exists so that owner scoping is something you have to opt *out*
of rather than remember to apply. Every read path in the product goes through
it, and the cost of forgetting is another user's unreleased film.
"""

from __future__ import annotations

import uuid
from collections.abc import Iterator
from typing import TypeVar

from fastapi import Request
from sqlalchemy import Select, select
from sqlalchemy.orm import Session, sessionmaker

from .models import Project

T = TypeVar("T")

_session_factory: sessionmaker[Session] | None = None


def configure_sessions(engine) -> sessionmaker[Session]:
    global _session_factory
    _session_factory = sessionmaker(bind=engine, expire_on_commit=False, autoflush=False)
    return _session_factory


def get_session(request: Request) -> Iterator[Session]:
    if _session_factory is None:
        configure_sessions(request.app.state.engine)
    assert _session_factory is not None
    session = _session_factory()
    try:
        yield session
        session.commit()
    except Exception:
        session.rollback()
        raise
    finally:
        session.close()


def owned_projects(owner_id: uuid.UUID) -> Select[tuple[Project]]:
    """Every project query starts here. Deleted projects are excluded."""
    return select(Project).where(
        Project.owner_id == owner_id,
        Project.deleted_at.is_(None),
    )
