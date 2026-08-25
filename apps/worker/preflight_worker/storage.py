"""Object storage for the worker.

The worker reaches Cloud Storage directly because it is the only component that
handles media. The API issues signed URLs and records evidence; it never opens a
file. Keeping that split means a compromised API cannot read customer masters,
and a compromised worker cannot reach project metadata it was not handed.

Every download lands in a temporary directory that is removed when the job ends,
including when it ends badly.
"""

from __future__ import annotations

import logging
import os
import re
from pathlib import Path

logger = logging.getLogger("preflight.worker.storage")


class StorageError(RuntimeError):
    pass


def _client():
    from google.cloud import storage

    bucket = os.environ.get("GCS_BUCKET", "")
    if not bucket:
        raise StorageError("GCS_BUCKET is not configured")
    return storage.Client(project=os.environ.get("GOOGLE_CLOUD_PROJECT") or None), bucket


_SAFE_KEY = re.compile(r"^[A-Za-z0-9][A-Za-z0-9._/-]{0,700}$")


def _check_key(key: str) -> str:
    """Refuse anything that is not a plain object key.

    Keys reach the worker over the network. A key containing `..` is not a typo
    to be normalised — it is an attempt to reach an object the job was not
    given, and it is rejected.
    """
    if not key or not _SAFE_KEY.match(key):
        raise StorageError(f"refusing malformed object key {key[:60]!r}")
    if ".." in key.split("/"):
        raise StorageError("refusing object key containing a parent reference")
    return key


def download(key: str, destination: Path) -> Path:
    """Fetch one object into the job's temporary workspace."""
    _check_key(key)
    client, bucket = _client()
    blob = client.bucket(bucket).get_blob(key)
    if blob is None:
        raise StorageError(f"source asset is missing from storage: {key}")

    destination.parent.mkdir(parents=True, exist_ok=True)
    blob.download_to_filename(str(destination))
    logger.info("downloaded %s (%s bytes)", key, destination.stat().st_size)
    return destination


def upload(path: Path, key: str, content_type: str | None = None) -> str:
    """Write a derived asset back to private storage.

    Overwrites deliberately: output keys are derived from the plan digest and
    step, so a retried job rewrites the same object rather than accumulating a
    second copy. That is what makes the job idempotent at the storage layer.
    """
    _check_key(key)
    client, bucket = _client()
    blob = client.bucket(bucket).blob(key)
    blob.upload_from_filename(str(path), content_type=content_type)
    logger.info("uploaded %s (%s bytes)", key, path.stat().st_size)
    return key


def derived_key(project_id: str, plan_digest: str, filename: str) -> str:
    """Where a repaired asset lives.

    Includes the plan digest so outputs from different plans never collide, and
    so a retry of the same plan lands on the same object.
    """
    safe = re.sub(r"[^A-Za-z0-9._-]", "_", filename)
    return _check_key(f"derived/{project_id}/{plan_digest[:16]}/{safe}")


def package_key(project_id: str, plan_digest: str, destination_id: str) -> str:
    safe = re.sub(r"[^A-Za-z0-9._-]", "_", destination_id)
    return _check_key(f"packages/{project_id}/{plan_digest[:16]}/{safe}.zip")


def write_zip(package_dir: Path, archive_path: Path) -> Path:
    """Zip a package directory with normalised, deterministic entries.

    Entry names come from the paths on disk, which were themselves produced by
    safe_package_name, so nothing user-controlled reaches the archive index.
    Sorting the entries keeps the archive reproducible.
    """
    import zipfile

    files = sorted(
        (p for p in package_dir.rglob("*") if p.is_file()),
        key=lambda p: p.relative_to(package_dir).as_posix(),
    )
    archive_path.parent.mkdir(parents=True, exist_ok=True)

    with zipfile.ZipFile(archive_path, "w", compression=zipfile.ZIP_DEFLATED) as zf:
        for path in files:
            arcname = path.relative_to(package_dir).as_posix()
            if arcname.startswith("/") or ".." in arcname.split("/"):
                raise StorageError(f"refusing archive entry {arcname!r}")
            zf.write(path, arcname)

    return archive_path
