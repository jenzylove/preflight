"""Database schema.

The schema lives in ``preflight_contracts`` rather than here because it is a
contract between the API and the worker, not something the API owns. The worker
needs to read and write these rows; it must not need the API's routers, auth or
provider clients to do so.

This module re-exports it so API call sites read naturally. The re-export is
generated from the shared module rather than hand-listed: an explicit list falls
out of step the moment a table is added, which is exactly how a new model
reached production and crashed the container on import.
"""

from __future__ import annotations

from preflight_contracts import models as _models

_EXPORTED = [
    name for name in dir(_models)
    if not name.startswith("_")
    and isinstance(getattr(_models, name), type)
    and hasattr(getattr(_models, name), "__tablename__")
]

for _name in _EXPORTED:
    globals()[_name] = getattr(_models, _name)

Base = _models.Base

__all__ = [*sorted(_EXPORTED), "Base"]


def __getattr__(name: str):
    """Fall through to the shared module for anything that is not a table."""
    try:
        return getattr(_models, name)
    except AttributeError as exc:
        raise AttributeError(f"module {__name__!r} has no attribute {name!r}") from exc
