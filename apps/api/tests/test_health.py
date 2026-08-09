"""Health contract.

A readiness probe that returns OK regardless of whether the database is
reachable is worse than having none: it turns an outage into a silent one.
These tests exist to stop that being introduced later.
"""

from __future__ import annotations

import pytest
from fastapi.testclient import TestClient
from preflight_api.main import app
from sqlalchemy.exc import OperationalError


@pytest.fixture
def client():
    with TestClient(app) as test_client:
        yield test_client


class _BrokenEngine:
    """Stands in for a database that is unreachable."""

    def connect(self):
        raise OperationalError("SELECT 1", {}, Exception("connection refused"))

    def dispose(self):
        pass


def test_liveness_does_not_depend_on_anything(client):
    response = client.get("/health/live")
    assert response.status_code == 200
    assert response.json()["status"] == "alive"


def test_readiness_reports_not_ready_when_the_database_is_unreachable(client):
    original = app.state.engine
    app.state.engine = _BrokenEngine()
    try:
        response = client.get("/health/ready")
        assert response.status_code == 503
        body = response.json()
        assert body["status"] == "not_ready"
        assert body["checks"]["database"] == "unavailable"
    finally:
        app.state.engine = original


def test_readiness_does_not_leak_provider_detail(client):
    """The probe says a dependency is unavailable, never why in provider terms.

    Echoing the driver's error would put hostnames, ports and sometimes
    credentials into logs and into an unauthenticated response body.
    """
    original = app.state.engine
    app.state.engine = _BrokenEngine()
    try:
        body = client.get("/health/ready").text.lower()
        for leaked in ("connection refused", "psycopg", "password", "5432", "select 1"):
            assert leaked not in body
    finally:
        app.state.engine = original


def test_unconfigured_providers_are_named_not_hidden(client):
    """A half-configured deployment should say so rather than fail later."""
    response = client.get("/health/ready")
    assert "unconfigured" in response.json()
