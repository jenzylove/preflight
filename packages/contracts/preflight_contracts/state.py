"""State machines for projects, packages and jobs.

Transitions are declared as data and enforced in one place. The important
property is negative: there is no transition into ``PackageState.VERIFIED``
that a worker can take. Verification is reached only through validation, and
only when the readiness predicate holds — so a worker that crashes, lies, or
exits zero having produced garbage cannot mark anything verified.
"""

from __future__ import annotations

from enum import Enum


class TransitionError(RuntimeError):
    """Raised on an attempt to move through an edge that does not exist."""


class ProjectState(str, Enum):
    DRAFT = "DRAFT"
    ASSETS_UPLOADED = "ASSETS_UPLOADED"
    DESTINATIONS_CONFIRMED = "DESTINATIONS_CONFIRMED"
    PREFLIGHT_COMPLETE = "PREFLIGHT_COMPLETE"
    REPAIR_APPROVED = "REPAIR_APPROVED"
    PROCESSING = "PROCESSING"
    PACKAGES_READY = "PACKAGES_READY"
    DELIVERED = "DELIVERED"
    DELETION_PENDING = "DELETION_PENDING"
    DELETED = "DELETED"


class PackageState(str, Enum):
    PLANNED = "PLANNED"
    BUILDING = "BUILDING"
    VALIDATING = "VALIDATING"
    VERIFIED = "VERIFIED"
    FAILED = "FAILED"
    SUPERSEDED = "SUPERSEDED"


class JobState(str, Enum):
    QUEUED = "QUEUED"
    RUNNING = "RUNNING"
    SUCCEEDED = "SUCCEEDED"
    FAILED = "FAILED"
    CANCELLED = "CANCELLED"


PROJECT_TRANSITIONS: dict[ProjectState, set[ProjectState]] = {
    ProjectState.DRAFT: {ProjectState.ASSETS_UPLOADED},
    ProjectState.ASSETS_UPLOADED: {
        ProjectState.DESTINATIONS_CONFIRMED,
        ProjectState.ASSETS_UPLOADED,   # more assets may be added
    },
    ProjectState.DESTINATIONS_CONFIRMED: {
        ProjectState.PREFLIGHT_COMPLETE,
        ProjectState.DESTINATIONS_CONFIRMED,
    },
    ProjectState.PREFLIGHT_COMPLETE: {
        ProjectState.REPAIR_APPROVED,
        # Re-running preflight after changing destinations must be possible.
        ProjectState.DESTINATIONS_CONFIRMED,
    },
    ProjectState.REPAIR_APPROVED: {ProjectState.PROCESSING},
    ProjectState.PROCESSING: {
        ProjectState.PACKAGES_READY,
        # A failed run returns to the plan, never straight to ready.
        ProjectState.PREFLIGHT_COMPLETE,
    },
    ProjectState.PACKAGES_READY: {
        ProjectState.DELIVERED,
        ProjectState.PREFLIGHT_COMPLETE,   # new destination added later
    },
    ProjectState.DELIVERED: {ProjectState.PREFLIGHT_COMPLETE},
    ProjectState.DELETION_PENDING: {ProjectState.DELETED, ProjectState.DELETION_PENDING},
    ProjectState.DELETED: set(),
}

PACKAGE_TRANSITIONS: dict[PackageState, set[PackageState]] = {
    PackageState.PLANNED: {PackageState.BUILDING, PackageState.SUPERSEDED},
    PackageState.BUILDING: {
        PackageState.VALIDATING,
        PackageState.FAILED,
        PackageState.SUPERSEDED,
    },
    # Note the absence: BUILDING cannot reach VERIFIED. Every path to
    # verification passes through independent validation.
    PackageState.VALIDATING: {
        PackageState.VERIFIED,
        PackageState.FAILED,
        PackageState.SUPERSEDED,
    },
    PackageState.VERIFIED: {PackageState.SUPERSEDED},
    PackageState.FAILED: {PackageState.BUILDING, PackageState.SUPERSEDED},
    PackageState.SUPERSEDED: set(),
}

JOB_TRANSITIONS: dict[JobState, set[JobState]] = {
    JobState.QUEUED: {JobState.RUNNING, JobState.CANCELLED},
    JobState.RUNNING: {JobState.SUCCEEDED, JobState.FAILED, JobState.CANCELLED},
    JobState.SUCCEEDED: set(),
    JobState.FAILED: {JobState.QUEUED},   # retry
    JobState.CANCELLED: set(),
}


def _check(table: dict, current, target, label: str):
    allowed = table.get(current, set())
    if target not in allowed:
        permitted = ", ".join(sorted(s.value for s in allowed)) or "nothing"
        raise TransitionError(
            f"{label}: cannot move from {current.value} to {target.value}; "
            f"permitted from {current.value}: {permitted}"
        )
    return target


def transition_project(current: ProjectState, target: ProjectState) -> ProjectState:
    # Deletion may be requested from any live state, so it is not enumerated
    # against every source above.
    if target is ProjectState.DELETION_PENDING and current is not ProjectState.DELETED:
        return target
    return _check(PROJECT_TRANSITIONS, current, target, "project")


def transition_package(current: PackageState, target: PackageState) -> PackageState:
    return _check(PACKAGE_TRANSITIONS, current, target, "package")


def transition_job(current: JobState, target: JobState) -> JobState:
    return _check(JOB_TRANSITIONS, current, target, "job")


def may_verify(
    *,
    required_assertions_all_pass: bool,
    any_required_ambiguous: bool,
    any_required_unsupported: bool,
    package_hash_present: bool,
    manifest_verified: bool,
    validated_against_output: bool,
    rule_pack_version_pinned: bool,
) -> tuple[bool, list[str]]:
    """The readiness predicate from PRD §13.

    Returns the decision and, when it is negative, the specific reasons — a
    user is owed the reason a package is not verified, not a bare refusal.

    ``validated_against_output`` exists because the most dangerous failure mode
    is validating the input and reporting it as the output. That produces a
    package that is confidently, provably wrong.
    """
    reasons: list[str] = []
    if not required_assertions_all_pass:
        reasons.append("a required rule is not satisfied")
    if any_required_ambiguous:
        reasons.append("a required rule is ambiguous")
    if any_required_unsupported:
        reasons.append("a required rule needs work Preflight cannot perform")
    if not package_hash_present:
        reasons.append("the package has no recorded hash")
    if not manifest_verified:
        reasons.append("manifest verification did not pass")
    if not validated_against_output:
        reasons.append("validation did not run against the produced output")
    if not rule_pack_version_pinned:
        reasons.append("the rule-pack version is not pinned in the passport")
    return (not reasons), reasons
