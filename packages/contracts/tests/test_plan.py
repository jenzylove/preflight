"""Repair planning and approval binding.

The central guarantee tested here: a user approves one exact plan, and any
change to that plan invalidates the approval. Without it, "approve" means
"approve whatever this becomes later", which is not consent.
"""

from __future__ import annotations

from preflight_contracts.compare import Assertion, Result
from preflight_contracts.plan import (
    OPERATION_CATALOGUE,
    Safety,
    approval_matches,
    build_plan,
)
from preflight_contracts.rules import AssetType, Severity


def assertion(
    field_name="integratedLoudnessLufs",
    asset=AssetType.AUDIO,
    result=Result.REPAIRABLE,
    operation="normalise_loudness",
    rule_id="r1",
    measured=-12.0,
    expected="between -21.0 and -18.0",
    explanation="",
) -> Assertion:
    return Assertion(
        rule_id=rule_id, destination_id="d", asset_type=asset, field_name=field_name,
        expected=expected, measured=measured, result=result,
        severity=Severity.REQUIRED, source_evidence_id="ev_1",
        repair_operation=operation, explanation=explanation,
    )


LOUDNESS = {"artdocfest": (-21.0, -18.0)}


class TestPlanConstruction:
    def test_a_repairable_failure_becomes_a_green_step(self):
        plan = build_plan({"artdocfest": [assertion()]}, loudness_targets=LOUDNESS)
        assert len(plan.green) == 1
        assert plan.green[0].operation == "normalise_loudness"

    def test_the_loudness_target_is_the_midpoint_of_the_published_window(self):
        plan = build_plan({"artdocfest": [assertion()]}, loudness_targets=LOUDNESS)
        assert plan.green[0].parameters["targetLufs"] == -19.5

    def test_a_passing_assertion_produces_no_work(self):
        plan = build_plan({"d": [assertion(result=Result.PASS)]})
        assert plan.steps == []

    def test_an_out_of_scope_conditional_rule_produces_no_work(self):
        plan = build_plan({"d": [assertion(result=Result.NOT_APPLICABLE, operation=None)]})
        assert plan.steps == [] and plan.blocked == []


class TestSafetyClassification:
    def test_re_encoding_is_never_green(self):
        plan = build_plan({
            "d": [assertion(
                field_name="bitrateBps", asset=AssetType.VIDEO,
                result=Result.REVIEW_REQUIRED, operation=None,
            )]
        })
        assert plan.green == []
        assert len(plan.needs_decision) == 1
        assert plan.needs_decision[0].safety is Safety.YELLOW

    def test_every_catalogued_operation_declares_its_safety(self):
        for name, spec in OPERATION_CATALOGUE.items():
            assert isinstance(spec["safety"], Safety), name
            assert spec["explains"].strip(), name

    def test_an_unsupported_failure_is_blocked_not_attempted(self):
        plan = build_plan({
            "d": [assertion(result=Result.UNSUPPORTED, operation=None,
                            explanation="needs professional mastering")]
        })
        assert plan.steps == []
        assert plan.blocked[0]["safety"] == "red"


class TestUnresolved:
    def test_an_ambiguous_requirement_asks_the_user_rather_than_guessing(self):
        plan = build_plan({"d": [assertion(result=Result.AMBIGUOUS, operation=None)]})
        assert plan.steps == []
        assert plan.unresolved[0]["needs"] == "your_confirmation"

    def test_an_unmeasured_property_is_reported_as_a_missing_asset(self):
        plan = build_plan({"d": [assertion(result=Result.NOT_MEASURED, operation=None)]})
        assert plan.unresolved[0]["needs"] == "missing_asset"


class TestReuse:
    def test_identical_work_for_two_destinations_is_done_once(self):
        """AC-5's economic half: don't rebuild what two destinations share."""
        subtitle = assertion(
            field_name="format", asset=AssetType.SUBTITLE,
            operation="convert_subtitles", expected="eq srt", measured="vtt",
        )
        plan = build_plan({"a": [subtitle], "b": [subtitle]})
        assert len(plan.green) == 1
        assert plan.reused

    def test_different_parameters_are_not_reused(self):
        plan = build_plan(
            {
                "a": [assertion(rule_id="r1")],
                "b": [assertion(rule_id="r2")],
            },
            loudness_targets={"a": (-21.0, -18.0), "b": (-25.0, -22.0)},
        )
        assert len(plan.green) == 2


class TestDigestAndApproval:
    def test_the_same_inputs_produce_the_same_digest(self):
        a = build_plan({"artdocfest": [assertion()]}, loudness_targets=LOUDNESS)
        b = build_plan({"artdocfest": [assertion()]}, loudness_targets=LOUDNESS)
        assert a.digest() == b.digest()

    def test_changing_a_parameter_changes_the_digest(self):
        """AC-6. The approval must not survive a change to what was approved."""
        original = build_plan({"artdocfest": [assertion()]}, loudness_targets=LOUDNESS)
        tampered = build_plan(
            {"artdocfest": [assertion()]}, loudness_targets={"artdocfest": (-25.0, -22.0)}
        )
        assert original.digest() != tampered.digest()
        assert not approval_matches(tampered.digest(), original.digest())

    def test_adding_a_step_changes_the_digest(self):
        one = build_plan({"d": [assertion()]}, loudness_targets={"d": (-21.0, -18.0)})
        two = build_plan(
            {"d": [
                assertion(),
                assertion(field_name="format", asset=AssetType.SUBTITLE,
                          operation="convert_subtitles", rule_id="r2",
                          expected="eq srt", measured="vtt"),
            ]},
            loudness_targets={"d": (-21.0, -18.0)},
        )
        assert one.digest() != two.digest()

    def test_an_empty_digest_never_matches(self):
        assert not approval_matches("", "")


class TestOrderingAndPreservation:
    def test_metadata_rewrite_follows_loudness_normalisation(self):
        """The container correction operates on the normalised file."""
        plan = build_plan(
            {"d": [
                assertion(),
                assertion(field_name="displayAspectRatio", asset=AssetType.VIDEO,
                          operation="rewrite_container_metadata", rule_id="r2",
                          expected="eq 16:9", measured="4:3"),
            ]},
            loudness_targets={"d": (-21.0, -18.0)},
        )
        operations = [s.operation for s in plan.steps]
        assert operations.index("normalise_loudness") < operations.index(
            "rewrite_container_metadata"
        )
        rewrite = next(s for s in plan.steps if s.operation == "rewrite_container_metadata")
        assert rewrite.depends_on

    def test_untouched_assets_are_reported_as_preserved(self):
        plan = build_plan({"d": [assertion()]}, loudness_targets={"d": (-21.0, -18.0)})
        preserved = plan.preserved_assets({"master", "poster", "subtitle", "metadata"})
        assert "poster" in preserved and "subtitle" in preserved

    def test_estimates_scale_with_runtime(self):
        plan = build_plan({"d": [assertion()]}, loudness_targets={"d": (-21.0, -18.0)})
        assert plan.estimated_seconds(600) > plan.estimated_seconds(60)
