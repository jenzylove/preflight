"""The negative cases are the point.

Most of these tests assert that something *cannot* happen. That is the whole
value of a state machine here: a package reaching VERIFIED by any route other
than passing validation would make every claim Preflight prints untrue.
"""

from __future__ import annotations

import pytest
from preflight_contracts.state import (
    JobState,
    PackageState,
    ProjectState,
    TransitionError,
    may_verify,
    transition_job,
    transition_package,
    transition_project,
)


class TestPackageVerification:
    def test_a_package_cannot_reach_verified_without_validating(self):
        # AC-7: a worker that exits successfully having produced a broken
        # output must not be able to declare the package good.
        with pytest.raises(TransitionError):
            transition_package(PackageState.BUILDING, PackageState.VERIFIED)

    def test_verification_is_reachable_only_from_validating(self):
        assert transition_package(PackageState.VALIDATING, PackageState.VERIFIED) is (
            PackageState.VERIFIED
        )

    def test_a_planned_package_cannot_skip_straight_to_verified(self):
        with pytest.raises(TransitionError):
            transition_package(PackageState.PLANNED, PackageState.VERIFIED)

    def test_a_failed_package_can_be_rebuilt(self):
        assert transition_package(PackageState.FAILED, PackageState.BUILDING)

    def test_a_superseded_package_is_terminal(self):
        with pytest.raises(TransitionError):
            transition_package(PackageState.SUPERSEDED, PackageState.BUILDING)


class TestReadinessPredicate:
    @staticmethod
    def _all_good(**overrides):
        base = dict(
            required_assertions_all_pass=True,
            any_required_ambiguous=False,
            any_required_unsupported=False,
            package_hash_present=True,
            manifest_verified=True,
            validated_against_output=True,
            rule_pack_version_pinned=True,
        )
        base.update(overrides)
        return base

    def test_everything_satisfied_verifies(self):
        ok, reasons = may_verify(**self._all_good())
        assert ok and reasons == []

    def test_validating_the_input_instead_of_the_output_blocks(self):
        ok, reasons = may_verify(**self._all_good(validated_against_output=False))
        assert not ok
        assert "validation did not run against the produced output" in reasons

    def test_ambiguity_blocks_even_when_everything_else_passes(self):
        ok, reasons = may_verify(**self._all_good(any_required_ambiguous=True))
        assert not ok
        assert "a required rule is ambiguous" in reasons

    def test_an_unpinned_rule_pack_blocks(self):
        ok, reasons = may_verify(**self._all_good(rule_pack_version_pinned=False))
        assert not ok

    def test_every_failure_reason_is_reported_not_just_the_first(self):
        ok, reasons = may_verify(
            **self._all_good(
                any_required_ambiguous=True,
                manifest_verified=False,
                package_hash_present=False,
            )
        )
        assert not ok
        assert len(reasons) == 3


class TestProjectLifecycle:
    def test_the_happy_path_is_walkable(self):
        order = [
            ProjectState.DRAFT, ProjectState.ASSETS_UPLOADED,
            ProjectState.DESTINATIONS_CONFIRMED, ProjectState.PREFLIGHT_COMPLETE,
            ProjectState.REPAIR_APPROVED, ProjectState.PROCESSING,
            ProjectState.PACKAGES_READY, ProjectState.DELIVERED,
        ]
        for current, target in zip(order, order[1:], strict=False):
            assert transition_project(current, target) is target

    def test_a_draft_cannot_jump_to_processing(self):
        with pytest.raises(TransitionError):
            transition_project(ProjectState.DRAFT, ProjectState.PROCESSING)

    def test_processing_cannot_skip_approval_on_a_second_run(self):
        with pytest.raises(TransitionError):
            transition_project(ProjectState.PREFLIGHT_COMPLETE, ProjectState.PROCESSING)

    def test_deletion_may_be_requested_from_any_live_state(self):
        for state in (ProjectState.DRAFT, ProjectState.PROCESSING, ProjectState.DELIVERED):
            assert transition_project(state, ProjectState.DELETION_PENDING) is (
                ProjectState.DELETION_PENDING
            )

    def test_a_deleted_project_cannot_be_resurrected(self):
        with pytest.raises(TransitionError):
            transition_project(ProjectState.DELETED, ProjectState.DRAFT)
        with pytest.raises(TransitionError):
            transition_project(ProjectState.DELETED, ProjectState.DELETION_PENDING)

    def test_the_error_names_what_was_permitted(self):
        with pytest.raises(TransitionError, match="permitted from DRAFT"):
            transition_project(ProjectState.DRAFT, ProjectState.DELIVERED)


class TestJobLifecycle:
    def test_a_failed_job_may_be_retried(self):
        assert transition_job(JobState.FAILED, JobState.QUEUED) is JobState.QUEUED

    def test_a_succeeded_job_is_terminal(self):
        with pytest.raises(TransitionError):
            transition_job(JobState.SUCCEEDED, JobState.RUNNING)

    def test_a_queued_job_cannot_report_success_without_running(self):
        with pytest.raises(TransitionError):
            transition_job(JobState.QUEUED, JobState.SUCCEEDED)
