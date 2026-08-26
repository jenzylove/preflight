"""Private object storage and signed access.

The web client never receives service credentials. It receives a short-lived
signed URL for one specific object, and nothing else. Storage keys are derived
from identifiers the server controls — never from a filename the user supplied,
which is where path traversal gets into object stores.
"""

from __future__ import annotations

import re
import uuid
from datetime import timedelta

from ..core.config import get_settings


class StorageError(RuntimeError):
    pass


#: What Preflight will accept, and what each type is allowed to be called.
#: Content type is verified against the file's actual bytes after upload;
#: this table is the first gate, not the only one.
ALLOWED_UPLOADS: dict[str, dict[str, object]] = {
    "master": {
        "content_types": {"video/mp4", "video/quicktime"},
        "extensions": {".mp4", ".mov"},
        "max_bytes": 2 * 1024 * 1024 * 1024,
    },
    "subtitle": {
        "content_types": {"text/vtt", "application/x-subrip", "text/plain"},
        "extensions": {".srt", ".vtt"},
        "max_bytes": 5 * 1024 * 1024,
    },
    "poster": {
        "content_types": {"image/jpeg", "image/png"},
        "extensions": {".jpg", ".jpeg", ".png"},
        "max_bytes": 50 * 1024 * 1024,
    },
}


def validate_upload(role: str, filename: str, content_type: str, byte_size: int) -> None:
    rules = ALLOWED_UPLOADS.get(role)
    if rules is None:
        raise StorageError(f"unsupported asset role {role!r}")

    extension = "." + filename.rsplit(".", 1)[-1].lower() if "." in filename else ""
    if extension not in rules["extensions"]:
        raise StorageError(
            f"{role} must be one of {', '.join(sorted(rules['extensions']))}"
        )
    if content_type not in rules["content_types"]:
        raise StorageError(f"{content_type} is not accepted for {role}")
    if byte_size <= 0:
        raise StorageError("file is empty")
    if byte_size > rules["max_bytes"]:
        limit_mb = int(rules["max_bytes"]) // (1024 * 1024)
        raise StorageError(f"{role} exceeds the {limit_mb} MB limit")


def storage_key(project_id: uuid.UUID, asset_id: uuid.UUID, role: str, extension: str) -> str:
    """Build an object key from server-controlled identifiers only.

    The user's filename is preserved in the database for display, but never
    reaches the object store. This removes an entire class of traversal and
    collision problems rather than trying to sanitise around them.
    """
    if not re.fullmatch(r"\.[a-z0-9]{1,5}", extension):
        raise StorageError(f"refusing to build a key with extension {extension!r}")
    return f"originals/{project_id}/{asset_id}/{role}{extension}"


def derived_key(project_id: uuid.UUID, asset_id: uuid.UUID, name: str) -> str:
    if not re.fullmatch(r"[a-z0-9][a-z0-9._-]{0,80}", name):
        raise StorageError(f"invalid derived object name {name!r}")
    return f"derived/{project_id}/{asset_id}/{name}"


def _client():
    from google.cloud import storage

    settings = get_settings()
    if not settings.gcs_bucket:
        raise StorageError("object storage is not configured")
    return storage.Client(project=settings.google_cloud_project), settings.gcs_bucket


def create_resumable_upload_url(key: str, content_type: str, max_bytes: int) -> str:
    """A single-use, expiring URL that can write exactly one object.

    Resumable so that a large master survives the kind of flaky connection
    that would otherwise force a producer to restart a two-hour upload.
    """
    client, bucket_name = _client()
    settings = get_settings()
    blob = client.bucket(bucket_name).blob(key)

    return blob.create_resumable_upload_session(
        content_type=content_type,
        size=max_bytes,
        origin=None,
        timeout=settings.signed_url_ttl_seconds,
    )


def create_download_url(key: str, filename: str) -> str:
    """Short-lived read URL. The bucket path never appears in the product UI."""
    client, bucket_name = _client()
    settings = get_settings()
    blob = client.bucket(bucket_name).blob(key)

    safe_filename = re.sub(r'[^A-Za-z0-9._-]', "_", filename)[:120] or "download"

    return blob.generate_signed_url(
        version="v4",
        expiration=timedelta(seconds=settings.signed_url_ttl_seconds),
        method="GET",
        response_disposition=f'attachment; filename="{safe_filename}"',
        **_signing_credentials(),
    )


def _signing_credentials() -> dict[str, str]:
    """What V4 signing needs when there is no private key on disk.

    On Cloud Run the runtime identity comes from the metadata server and holds
    no key material, so the library cannot sign locally. It can instead ask IAM
    to sign on the service account's behalf, which is why the account carries
    serviceAccountTokenCreator. A key file mounted into the container would
    also work and would be a worse idea: it would put a long-lived credential
    on disk in the service that faces the internet.

    Returns nothing when the credentials can already sign - locally, where a
    key file is configured - so the same code path works in both places.
    """
    import google.auth
    import google.auth.transport.requests

    credentials, _ = google.auth.default()

    if hasattr(credentials, "signer_email") and getattr(credentials, "signer", None):
        return {}

    credentials.refresh(google.auth.transport.requests.Request())
    email = getattr(credentials, "service_account_email", None)
    if not email or email == "default":
        raise StorageError("no service account identity available to sign with")

    return {"service_account_email": email, "access_token": credentials.token}


def object_exists(key: str) -> tuple[bool, int]:
    client, bucket_name = _client()
    blob = client.bucket(bucket_name).get_blob(key)
    return (blob is not None), (blob.size or 0 if blob else 0)


def delete_object(key: str) -> bool:
    """Delete one object. Missing is success — deletion is idempotent."""
    from google.api_core import exceptions as gcp_exceptions

    client, bucket_name = _client()
    try:
        client.bucket(bucket_name).blob(key).delete()
        return True
    except gcp_exceptions.NotFound:
        return True
    except gcp_exceptions.GoogleAPIError:
        return False
