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


class TestBrowserCanReachTheApi:
    """The browser is a first-class client, not an afterthought.

    The workspace holds the ID token and makes every product call from the
    page, so every request it sends is cross-origin. Without CORS the browser
    refuses at the preflight and the entire authenticated product is
    unreachable — which is exactly what shipped, and what no server-side test
    could catch, because Python clients do not send an Origin header.
    """

    def test_a_preflight_from_the_web_app_is_allowed(self, client):
        from preflight_api.core.config import get_settings

        origin = get_settings().allowed_origins[0]
        response = client.options(
            "/v1/projects",
            headers={
                "Origin": origin,
                "Access-Control-Request-Method": "GET",
                "Access-Control-Request-Headers": "authorization",
            },
        )
        assert response.status_code == 200
        assert response.headers["access-control-allow-origin"] == origin

    def test_authorization_survives_the_preflight(self, client):
        """A rejected Authorization header would break every product call."""
        origin = __import__(
            "preflight_api.core.config", fromlist=["get_settings"]
        ).get_settings().allowed_origins[0]
        response = client.options(
            "/v1/projects",
            headers={
                "Origin": origin,
                "Access-Control-Request-Method": "POST",
                "Access-Control-Request-Headers": "authorization,content-type",
            },
        )
        allowed = response.headers.get("access-control-allow-headers", "").lower()
        assert "authorization" in allowed

    def test_an_unknown_origin_is_not_granted_access(self, client):
        """Explicit origins, never a wildcard. This API serves unreleased films."""
        response = client.options(
            "/v1/projects",
            headers={
                "Origin": "https://not-preflight.example",
                "Access-Control-Request-Method": "GET",
            },
        )
        assert response.headers.get("access-control-allow-origin") not in (
            "*",
            "https://not-preflight.example",
        )
