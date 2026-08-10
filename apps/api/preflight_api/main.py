"""Preflight API.

Phase 1 establishes the service boundary and the health contract. Feature
routers arrive in later phases; what matters here is that readiness tells the
truth from the first commit, because a readiness probe that always returns OK
is worse than none at all.
"""

from __future__ import annotations

import logging
from contextlib import asynccontextmanager

from fastapi import FastAPI, Response, status
from sqlalchemy import create_engine, text
from sqlalchemy.exc import SQLAlchemyError

from .assets.router import router as assets_router
from .core.config import get_settings
from .core.db import configure_sessions
from .preflight.execute import router as execute_router
from .preflight.router import router as preflight_router
from .projects.router import router as projects_router

logger = logging.getLogger("preflight")

API_VERSION = "0.1.0"


@asynccontextmanager
async def lifespan(app: FastAPI):
    settings = get_settings()
    missing = settings.missing_for_full_operation()
    if missing:
        logger.warning(
            "starting with unconfigured providers: %s — "
            "requirement retrieval and uploads will be unavailable",
            ", ".join(missing),
        )
    app.state.engine = create_engine(settings.database_url, pool_pre_ping=True, pool_size=5)
    configure_sessions(app.state.engine)
    try:
        yield
    finally:
        app.state.engine.dispose()


app = FastAPI(
    title="Preflight API",
    version=API_VERSION,
    description=(
        "Destination-aware delivery compliance. Preflight verifies media "
        "against published requirements; it does not guarantee that any "
        "recipient will accept a delivery."
    ),
    lifespan=lifespan,
)


app.include_router(projects_router)
app.include_router(assets_router)
app.include_router(preflight_router)
app.include_router(execute_router)


@app.get("/health/live", tags=["ops"])
def live() -> dict[str, str]:
    """Liveness only — the process is running. Deliberately checks nothing else."""
    return {"status": "alive", "version": API_VERSION}


@app.get("/health/ready", tags=["ops"])
def ready(response: Response) -> dict[str, object]:
    """Readiness crosses the real database boundary.

    On failure it reports *that* the dependency is unavailable without echoing
    the provider's error, which would leak hostnames and credentials into logs
    and responses.
    """
    settings = get_settings()
    checks: dict[str, str] = {}

    try:
        with app.state.engine.connect() as connection:
            connection.execute(text("SELECT 1"))
        checks["database"] = "ok"
    except SQLAlchemyError:
        logger.exception("readiness: database check failed")
        checks["database"] = "unavailable"

    missing = settings.missing_for_full_operation()
    checks["providers"] = "ok" if not missing else "unconfigured"

    healthy = checks["database"] == "ok"
    if not healthy:
        response.status_code = status.HTTP_503_SERVICE_UNAVAILABLE

    return {
        "status": "ready" if healthy else "not_ready",
        "version": API_VERSION,
        "checks": checks,
        "unconfigured": missing,
    }
