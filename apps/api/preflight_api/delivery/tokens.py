"""Delivery tokens.

Only the hash of a token is stored. A leaked database yields no working links,
because the token itself exists in exactly two places: the URL the user copies,
and nowhere else.

Lookup is by hash, which is also why the tokens are long and random rather than
short and memorable — there is no rate limit that makes a guessable token safe.
"""

from __future__ import annotations

import hashlib
import hmac
import secrets
from datetime import UTC, datetime, timedelta

#: 32 bytes, URL-safe. Long enough that enumeration is not a threat model.
TOKEN_BYTES = 32


def issue_token() -> tuple[str, str]:
    """Return (token, token_hash). The token is never stored or logged."""
    token = secrets.token_urlsafe(TOKEN_BYTES)
    return token, hash_token(token)


def hash_token(token: str) -> str:
    return hashlib.sha256(token.encode()).hexdigest()


def tokens_match(token: str, stored_hash: str) -> bool:
    """Constant-time comparison.

    A timing difference here leaks how much of a guessed token was correct,
    which turns an infeasible search into a feasible one.
    """
    return hmac.compare_digest(hash_token(token), stored_hash)


def expiry_from_now(hours: int) -> datetime:
    return datetime.now(UTC) + timedelta(hours=hours)


def is_usable(expires_at: datetime, revoked_at: datetime | None) -> tuple[bool, str]:
    """Whether a room may be opened, and why not if not.

    The reason is for logs and the owner's view. Recipients are told only that
    the link is not available — distinguishing 'expired' from 'revoked' from
    'never existed' tells an attacker which tokens are real.
    """
    if revoked_at is not None:
        return False, "revoked"
    if expires_at.tzinfo is None:
        expires_at = expires_at.replace(tzinfo=UTC)
    if expires_at <= datetime.now(UTC):
        return False, "expired"
    return True, "active"
