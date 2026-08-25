"""Authentication and ownership.

Two rules, both load-bearing:

  * Identity is derived from a verified token. No endpoint accepts an owner id
    from a request body, path or query string — there is deliberately no code
    path that could.
  * A resource belonging to someone else returns 404, never 403. A 403 confirms
    the resource exists, which is enough to enumerate other people's projects.
"""

from __future__ import annotations

import logging
import uuid

from fastapi import Depends, HTTPException, Request, status
from sqlalchemy import select
from sqlalchemy.orm import Session

from ..core.config import get_settings
from ..core.db import get_session
from ..core.models import Project, User

logger = logging.getLogger("preflight.auth")

NOT_FOUND = HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Not found")


class TokenVerificationError(Exception):
    """The token itself did not verify."""


class MisconfiguredAuthError(Exception):
    """Authentication could not be completed for reasons that are our fault.

    Kept separate from TokenVerificationError because the two demand opposite
    responses. A bad token is the caller's problem and gets a terse 401. A
    misconfigured service account is our problem, and returning 401 for it
    would tell every user their credentials are wrong while the real cause sits
    invisible in an IAM policy.
    """


def _verify_firebase_token(token: str, project_id: str) -> dict[str, str]:
    """Verify a Firebase ID token against Google's public keys.

    Delegated to the Firebase Admin SDK, which checks signature, expiry,
    issuer and audience. Rolling our own JWT verification here would be the
    kind of mistake that is invisible until it is catastrophic.
    """
    import firebase_admin
    from firebase_admin import auth as firebase_auth
    from firebase_admin import credentials

    if not firebase_admin._apps:
        firebase_admin.initialize_app(
            credentials.ApplicationDefault(), {"projectId": project_id}
        )

    try:
        decoded = firebase_auth.verify_id_token(token, check_revoked=True)
    except firebase_auth.InsufficientPermissionError as exc:
        # The token may be perfectly valid; the *service account* cannot query
        # revocation state. Rejecting the user here would be correct-by-accident
        # and impossible to diagnose, because the rejection looks identical to a
        # forged token. Fail loudly as a misconfiguration instead.
        raise MisconfiguredAuthError(
            "the runtime service account cannot check token revocation; "
            "it needs roles/firebaseauth.admin"
        ) from exc
    except Exception as exc:  # noqa: BLE001 - provider raises a wide family
        raise TokenVerificationError(str(exc)) from exc

    subject = decoded.get("uid") or decoded.get("sub")
    if not subject:
        raise TokenVerificationError("token carries no subject")
    return {"subject": subject, "email": decoded.get("email", "")}


def _bearer_token(request: Request) -> str:
    header = request.headers.get("authorization", "")
    scheme, _, token = header.partition(" ")
    if scheme.lower() != "bearer" or not token:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Authentication required",
            headers={"WWW-Authenticate": "Bearer"},
        )
    return token


def current_user(
    request: Request,
    session: Session = Depends(get_session),
) -> User:
    """Resolve the authenticated user, creating their record on first sight."""
    settings = get_settings()
    token = _bearer_token(request)

    if not settings.firebase_project_id:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="Authentication is not configured",
        )

    try:
        claims = _verify_firebase_token(token, settings.firebase_project_id)
    except MisconfiguredAuthError:
        logger.exception("authentication is misconfigured")
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="Sign-in is temporarily unavailable. This is not a problem "
                   "with your account.",
        ) from None
    except TokenVerificationError:
        # Logged without the token itself. A rejected token in a log file is
        # still a credential.
        logger.warning("rejected an invalid authentication token")
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Authentication failed",
            headers={"WWW-Authenticate": "Bearer"},
        ) from None

    user = session.scalar(select(User).where(User.auth_subject == claims["subject"]))
    if user is None:
        user = User(auth_subject=claims["subject"], email=claims["email"])
        session.add(user)
        session.flush()
    return user


def owned_project(
    project_id: uuid.UUID,
    user: User = Depends(current_user),
    session: Session = Depends(get_session),
) -> Project:
    """Load a project the caller owns, or 404.

    Deliberately indistinguishable from a project that does not exist.
    """
    project = session.scalar(
        select(Project).where(
            Project.id == project_id,
            Project.owner_id == user.id,
            Project.deleted_at.is_(None),
        )
    )
    if project is None:
        raise NOT_FOUND
    return project
