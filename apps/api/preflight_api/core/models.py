"""Database schema.

The schema lives in ``preflight_contracts`` rather than here because it is a
contract between the API and the worker, not something the API owns. The worker
needs to read and write these rows; it must not need the API's routers, auth or
provider clients to do so. Re-exported at the old path so call sites read
naturally from inside the API.
"""

from __future__ import annotations

from preflight_contracts.models import (
    Approval,
    Asset,
    AssetEvidence,
    Base,
    DeletionRequest,
    DeliveryEvent,
    DeliveryRoom,
    Destination,
    Job,
    Package,
    Passport,
    PreflightRun,
    Project,
    ProjectDestination,
    RepairPlan,
    RepairStep,
    RulePackRow,
    RuleRow,
    SourceEvidenceRow,
    User,
)

Assertion = __import__(
    "preflight_contracts.models", fromlist=["Assertion"]
).Assertion

__all__ = [
    "Approval", "Assertion", "Asset", "AssetEvidence", "Base", "DeletionRequest",
    "DeliveryEvent", "DeliveryRoom", "Destination", "Job", "Package", "Passport",
    "PreflightRun", "Project", "ProjectDestination", "RepairPlan", "RepairStep",
    "RulePackRow", "RuleRow", "SourceEvidenceRow", "User",
]
