"""Delivery token safety.

The delivery room is the only unauthenticated surface in Preflight, and it
points at unreleased films. These tests cover the properties that make that
acceptable.
"""

from __future__ import annotations

from datetime import UTC, datetime, timedelta

from preflight_api.delivery import tokens


class TestTokenIssuance:
    def test_the_token_is_not_recoverable_from_what_is_stored(self):
        token, stored = tokens.issue_token()
        assert token not in stored
        assert len(stored) == 64          # sha256 hex
        assert len(token) >= 40           # 32 random bytes, url-safe

    def test_every_token_is_unique(self):
        issued = {tokens.issue_token()[0] for _ in range(200)}
        assert len(issued) == 200

    def test_a_token_verifies_against_its_own_hash(self):
        token, stored = tokens.issue_token()
        assert tokens.tokens_match(token, stored)

    def test_a_different_token_does_not_verify(self):
        _, stored = tokens.issue_token()
        other, _ = tokens.issue_token()
        assert not tokens.tokens_match(other, stored)

    def test_a_near_miss_does_not_verify(self):
        token, stored = tokens.issue_token()
        assert not tokens.tokens_match(token[:-1] + ("A" if token[-1] != "A" else "B"), stored)

    def test_an_empty_token_does_not_verify(self):
        _, stored = tokens.issue_token()
        assert not tokens.tokens_match("", stored)


class TestUsability:
    def test_a_live_room_is_usable(self):
        usable, state = tokens.is_usable(datetime.now(UTC) + timedelta(hours=1), None)
        assert usable and state == "active"

    def test_an_expired_room_is_not_usable(self):
        """AC-10."""
        usable, state = tokens.is_usable(datetime.now(UTC) - timedelta(seconds=1), None)
        assert not usable and state == "expired"

    def test_a_revoked_room_is_not_usable_even_before_expiry(self):
        usable, state = tokens.is_usable(
            datetime.now(UTC) + timedelta(days=30), datetime.now(UTC)
        )
        assert not usable and state == "revoked"

    def test_revocation_takes_precedence_over_expiry(self):
        _, state = tokens.is_usable(
            datetime.now(UTC) - timedelta(days=1), datetime.now(UTC) - timedelta(days=2)
        )
        assert state == "revoked"

    def test_a_naive_expiry_is_treated_as_utc_rather_than_crashing(self):
        """Databases hand back naive datetimes; that must not become an outage."""
        usable, _ = tokens.is_usable(datetime.now(UTC).replace(tzinfo=None)
                                     + timedelta(hours=1), None)
        assert usable

    def test_expiry_is_computed_forward_from_now(self):
        assert tokens.expiry_from_now(24) > datetime.now(UTC) + timedelta(hours=23)
