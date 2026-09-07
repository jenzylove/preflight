"""Approval must stop applying when the requirements behind it change.

Setting a misread requirement aside is the one action Preflight asks of a user
when extraction gets a rule wrong. It changes what is blocked without changing
any step, so a digest taken over the steps alone stayed identical - the API
treated the plan as already executing, returned the existing job, and the
package kept the verdict and the limitations it had before the decision.
Nothing the person did had any effect, and the product still told them to do
it.

These tests pin the property that makes the loop work: two plans that differ in
what they leave outstanding are not the same plan.
"""

from __future__ import annotations

from preflight_contracts.plan import Plan, Safety, Step


def _step(operation: str = "normalise_loudness") -> Step:
    return Step(
        step_id="s1",
        operation=operation,
        safety=Safety.GREEN,
        destination_id="artdocfest",
        input_role="master",
        output_role="master_audio_corrected",
        parameters={"targetLufs": -19.5, "mode": "linear"},
        resolves=("r001",),
    )


def _blocked(field: str) -> dict:
    return {
        "destination": "artdocfest",
        "field": field,
        "published": "[25.0, 30.0]",
        "measured": 23.1,
        "reason": "No supported operation satisfies this requirement.",
        "safety": Safety.RED.value,
    }


def _unresolved(field: str) -> dict:
    return {
        "destination": "artdocfest",
        "field": field,
        "reason": "This property was not measured on the assets supplied.",
        "needs": "missing_asset",
    }


class TestOutstandingRequirementsAreInTheDigest:
    def test_setting_a_requirement_aside_changes_the_digest(self):
        """The exact regression: same work, one fewer blocked requirement."""
        before = Plan(steps=[_step()], blocked=[_blocked("audio.loudnessRangeLu")])
        after = Plan(steps=[_step()], blocked=[])
        assert before.digest() != after.digest()

    def test_an_unresolved_requirement_also_counts(self):
        before = Plan(steps=[_step()], unresolved=[_unresolved("package.fileNamePattern")])
        after = Plan(steps=[_step()], unresolved=[])
        assert before.digest() != after.digest()

    def test_a_different_blocked_field_is_a_different_plan(self):
        one = Plan(steps=[_step()], blocked=[_blocked("audio.loudnessRangeLu")])
        two = Plan(steps=[_step()], blocked=[_blocked("audio.truePeakDbtp")])
        assert one.digest() != two.digest()

    def test_the_same_plan_still_digests_the_same(self):
        """Approval must survive a re-run that genuinely changed nothing."""
        one = Plan(steps=[_step()], blocked=[_blocked("audio.loudnessRangeLu")])
        two = Plan(steps=[_step()], blocked=[_blocked("audio.loudnessRangeLu")])
        assert one.digest() == two.digest()

    def test_order_does_not_matter(self):
        a, b = _blocked("audio.loudnessRangeLu"), _blocked("audio.truePeakDbtp")
        assert Plan(steps=[_step()], blocked=[a, b]).digest() == \
               Plan(steps=[_step()], blocked=[b, a]).digest()

    def test_the_steps_still_drive_the_digest(self):
        """Adding the outstanding set must not stop steps from mattering."""
        assert Plan(steps=[_step("normalise_loudness")]).digest() != \
               Plan(steps=[_step("convert_subtitles")]).digest()

    def test_a_plan_with_nothing_outstanding_is_stable(self):
        assert Plan(steps=[_step()]).digest() == Plan(steps=[_step()]).digest()
