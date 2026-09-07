"""The browser must be able to finish an upload it is allowed to start.

Cloud Storage attaches CORS headers to a resumable session only when the
session was opened with the origin that will use it. Opened without one, the
returned URL is unusable from a browser: every PUT is blocked for want of an
'Access-Control-Allow-Origin' header, and the product cannot accept a file at
all. It shipped that way, and nothing caught it, because every automated
client uploads happily - they send no Origin header, so CORS never applies.

These tests pin the decision rather than the transport, which is the part that
can silently regress.
"""

from __future__ import annotations

from preflight_api.assets.storage import upload_session_origin

WEB = "https://preflight-web-584136898465.us-central1.run.app"
ALLOWED = [WEB]


def test_a_trusted_browser_gets_a_session_it_can_use():
    """The bug: this returned None, so the upload could never complete."""
    assert upload_session_origin(WEB, ALLOWED) == WEB


def test_an_untrusted_origin_is_not_given_a_session_of_its_own():
    """A session URL is writable by the origin it was opened for."""
    assert upload_session_origin("https://not-preflight.example", ALLOWED) is None


def test_a_client_with_no_origin_can_still_upload():
    """Server-side callers send no Origin, and must not be locked out."""
    assert upload_session_origin(None, ALLOWED) is None


def test_an_empty_origin_header_is_not_treated_as_trusted():
    assert upload_session_origin("", ALLOWED) is None


def test_the_allowlist_is_matched_exactly():
    """Prefix or substring matching would let a lookalike domain through."""
    for pretender in (
        f"{WEB}.evil.example",
        "https://preflight-web-584136898465.us-central1.run.app.attacker.test",
        "http://preflight-web-584136898465.us-central1.run.app",
    ):
        assert upload_session_origin(pretender, ALLOWED) is None


def test_every_origin_the_api_trusts_can_open_a_session():
    """The two lists are the same list. If they drift, uploads break."""
    from preflight_api.core.config import get_settings

    allowed = get_settings().allowed_origins
    assert allowed, "the API trusts no origin at all"
    for origin in allowed:
        assert upload_session_origin(origin, allowed) == origin
