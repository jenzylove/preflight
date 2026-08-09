from __future__ import annotations

import pytest

from preflight_contracts.compare import (
    ConflictStrength, Result, comparison_digest, evaluate, find_conflicts, is_ready,
)
from preflight_contracts.rules import (
    AssetType, Confidence, Operator, Rule, RulePack, Severity, SourceEvidence, TrustTier,
)


def rule(field_name="integratedLoudnessLufs", op=Operator.BETWEEN, value=(-21.0, -18.0),
         asset=AssetType.AUDIO, severity=Severity.REQUIRED, confidence=Confidence.HIGH,
         rid="r1") -> Rule:
    return Rule(rid, asset, field_name, op, list(value) if isinstance(value, tuple) else value,
                severity, "ev_1", confidence)


class TestComparison:
    def test_value_inside_the_published_range_passes(self):
        assert evaluate(rule(), {"integratedLoudnessLufs": -19.5}, "d").result is Result.PASS

    def test_value_outside_the_range_is_repairable_by_a_green_operation(self):
        result = evaluate(rule(), {"integratedLoudnessLufs": -14.2}, "d")
        assert result.result is Result.REPAIRABLE
        assert result.repair_operation == "normalise_loudness"

    def test_bitrate_failure_needs_review_because_it_re_encodes(self):
        assertion = evaluate(
            rule("bitrateBps", Operator.BETWEEN, (20_000_000, 30_000_000), AssetType.VIDEO),
            {"bitrateBps": 8_000_000}, "d",
        )
        assert assertion.result is Result.REVIEW_REQUIRED
        assert assertion.repair_operation is None

    def test_unmeasured_property_is_reported_not_assumed_passing(self):
        assert evaluate(rule(), {}, "d").result is Result.NOT_MEASURED

    def test_codec_aliases_are_normalised(self):
        assertion = evaluate(
            rule("codec", Operator.EQ, "h264", AssetType.VIDEO), {"codec": "AVC"}, "d"
        )
        assert assertion.result is Result.PASS


class TestAmbiguity:
    def test_conflicting_sources_block_rather_than_guess(self):
        assertion = evaluate(
            rule(), {"integratedLoudnessLufs": -19.0}, "d",
            ambiguous_rule_ids=frozenset({"r1"}),
        )
        # AC-8: a value that would otherwise pass must not be certified when
        # the requirement itself is contested.
        assert assertion.result is Result.AMBIGUOUS

    def test_low_confidence_mandatory_rule_is_ambiguous(self):
        assertion = evaluate(
            rule(confidence=Confidence.LOW), {"integratedLoudnessLufs": -19.0}, "d"
        )
        assert assertion.result is Result.AMBIGUOUS


class TestReadiness:
    def test_readiness_requires_every_mandatory_rule_to_pass(self):
        passing = evaluate(rule(), {"integratedLoudnessLufs": -19.0}, "d")
        failing = evaluate(rule(rid="r2"), {"integratedLoudnessLufs": -5.0}, "d")
        assert is_ready([passing])
        assert not is_ready([passing, failing])

    def test_a_failing_recommendation_does_not_block_readiness(self):
        passing = evaluate(rule(), {"integratedLoudnessLufs": -19.0}, "d")
        advisory = evaluate(
            rule(rid="r2", severity=Severity.RECOMMENDED), {"integratedLoudnessLufs": -5.0}, "d"
        )
        assert is_ready([passing, advisory])

    def test_ambiguity_blocks_readiness(self):
        assertion = evaluate(
            rule(), {"integratedLoudnessLufs": -19.0}, "d", frozenset({"r1"})
        )
        assert not is_ready([assertion])


class TestDeterminism:
    def test_equivalent_inputs_produce_the_same_digest(self):
        a = [evaluate(rule(), {"integratedLoudnessLufs": -19.0}, "d")]
        b = [evaluate(rule(), {"integratedLoudnessLufs": -19.0}, "d")]
        assert comparison_digest(a) == comparison_digest(b)

    def test_a_different_measurement_produces_a_different_digest(self):
        a = [evaluate(rule(), {"integratedLoudnessLufs": -19.0}, "d")]
        b = [evaluate(rule(), {"integratedLoudnessLufs": -14.0}, "d")]
        assert comparison_digest(a) != comparison_digest(b)


class TestConflictDetection:
    @staticmethod
    def _pack(dest: str, r: Rule) -> RulePack:
        ev = SourceEvidence(
            "ev_1", f"https://{dest}.example/spec", "2026-08-09T00:00:00+00:00",
            "h", "quoted requirement", TrustTier.OFFICIAL,
        )
        return RulePack(dest, 1, [r], {"ev_1": ev})

    def test_disjoint_numeric_ranges_are_a_hard_conflict(self):
        a = self._pack("a", rule("bitrateBps", Operator.BETWEEN, (20_000_000, 30_000_000),
                                 AssetType.VIDEO))
        b = self._pack("b", rule("bitrateBps", Operator.LTE, 8_000_000, AssetType.VIDEO, rid="r2"))
        conflicts = find_conflicts([a, b])
        assert len(conflicts) == 1
        assert conflicts[0]["strength"] == ConflictStrength.HARD.value

    def test_a_recommendation_colliding_with_a_mandate_is_a_soft_conflict(self):
        a = self._pack("a", rule("bitrateBps", Operator.BETWEEN, (20_000_000, 30_000_000),
                                 AssetType.VIDEO))
        b = self._pack("b", rule("bitrateBps", Operator.EQ, 8_000_000, AssetType.VIDEO,
                                 severity=Severity.RECOMMENDED, rid="r2"))
        conflicts = find_conflicts([a, b])
        assert len(conflicts) == 1
        assert conflicts[0]["strength"] == ConflictStrength.SOFT.value

    def test_overlapping_requirements_are_not_reported_as_a_conflict(self):
        a = self._pack("a", rule("codec", Operator.IN, ["aac", "ac3"], AssetType.AUDIO))
        b = self._pack("b", rule("codec", Operator.IN, ["aac", "opus"], AssetType.AUDIO, rid="r2"))
        assert find_conflicts([a, b]) == []

    def test_context_rules_never_produce_conflicts(self):
        a = self._pack("a", rule("bitrateBps", Operator.BETWEEN, (20_000_000, 30_000_000),
                                 AssetType.VIDEO))
        b = self._pack("b", rule("bitrateBps", Operator.EQ, 8_000_000, AssetType.VIDEO,
                                 severity=Severity.CONTEXT, rid="r2"))
        assert find_conflicts([a, b]) == []
