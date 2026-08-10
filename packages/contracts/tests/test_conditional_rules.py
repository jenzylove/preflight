"""Conditional requirements.

Real specifications are conditional. Artdocfest publishes 20-30 Mbps for
FullHD and 90-120 Mbps for 4K in the same table. Read flatly those are a
contradiction, and a system that reported them as one would block every
delivery on an ambiguity that does not exist.
"""

from __future__ import annotations

import pytest
from preflight_contracts.compare import Result, evaluate, find_conflicts
from preflight_contracts.rules import (
    AssetType,
    Confidence,
    Operator,
    Rule,
    RulePack,
    RuleRejected,
    Severity,
    SourceEvidence,
    TrustTier,
    build_rule,
)


def bitrate_rule(rid, low, high, height) -> Rule:
    return Rule(
        rid, AssetType.VIDEO, "bitrateBps", Operator.BETWEEN, [low, high],
        Severity.REQUIRED, "ev_1", Confidence.HIGH,
        applies_when={"heightPx": height},
    )


class TestScoping:
    def test_a_rule_applies_when_its_condition_matches(self):
        rule = bitrate_rule("r1", 20_000_000, 30_000_000, 1080)
        result = evaluate(rule, {"bitrateBps": 25_000_000, "heightPx": 1080}, "d")
        assert result.result is Result.PASS

    def test_a_rule_is_out_of_scope_when_its_condition_does_not_match(self):
        """The 4K bitrate rule must not fail a 1080p delivery."""
        rule = bitrate_rule("r1", 90_000_000, 120_000_000, 2160)
        result = evaluate(rule, {"bitrateBps": 25_000_000, "heightPx": 1080}, "d")
        assert result.result is Result.NOT_APPLICABLE
        assert "applies only when" in result.explanation

    def test_an_in_scope_rule_still_fails_when_violated(self):
        rule = bitrate_rule("r1", 20_000_000, 30_000_000, 1080)
        result = evaluate(rule, {"bitrateBps": 8_000_000, "heightPx": 1080}, "d")
        assert result.result is Result.REVIEW_REQUIRED

    def test_an_unmeasurable_condition_leaves_the_rule_out_of_scope(self):
        rule = bitrate_rule("r1", 20_000_000, 30_000_000, 1080)
        assert evaluate(rule, {"bitrateBps": 25_000_000}, "d").result is (
            Result.NOT_APPLICABLE
        )

    def test_a_condition_may_list_several_acceptable_values(self):
        rule = Rule(
            "r1", AssetType.VIDEO, "bitrateBps", Operator.GTE, 20_000_000,
            Severity.REQUIRED, "ev_1", Confidence.HIGH,
            applies_when={"heightPx": [1080, 1440]},
        )
        assert rule.applies_to({"heightPx": 1440})
        assert not rule.applies_to({"heightPx": 2160})

    def test_an_unconditional_rule_always_applies(self):
        rule = Rule(
            "r1", AssetType.VIDEO, "codec", Operator.EQ, "h264",
            Severity.REQUIRED, "ev_1", Confidence.HIGH,
        )
        assert rule.applies_to({})


class TestConflictScoping:
    @staticmethod
    def _pack(dest: str, rule: Rule) -> RulePack:
        evidence = SourceEvidence(
            "ev_1", f"https://{dest}.example/spec", "2026-08-10T00:00:00+00:00",
            "h", "quoted requirement", TrustTier.OFFICIAL,
        )
        return RulePack(dest, 1, [rule], {"ev_1": evidence})

    def test_differently_scoped_rules_do_not_conflict(self):
        """The finding that forced this feature to exist."""
        fhd = self._pack("a", bitrate_rule("r1", 20_000_000, 30_000_000, 1080))
        uhd = self._pack("b", bitrate_rule("r2", 90_000_000, 120_000_000, 2160))
        assert find_conflicts([fhd, uhd]) == []

    def test_identically_scoped_rules_still_conflict(self):
        a = self._pack("a", bitrate_rule("r1", 20_000_000, 30_000_000, 1080))
        b = self._pack("b", bitrate_rule("r2", 4_000_000, 8_000_000, 1080))
        assert len(find_conflicts([a, b])) == 1

    def test_a_condition_changes_the_rule_digest(self):
        scoped = bitrate_rule("r1", 20_000_000, 30_000_000, 1080)
        other = bitrate_rule("r1", 20_000_000, 30_000_000, 2160)
        assert scoped.digest() != other.digest()


class TestConditionValidation:
    @staticmethod
    def _evidence() -> SourceEvidence:
        return SourceEvidence(
            "ev_1", "https://x.example", "2026-08-10T00:00:00+00:00",
            "h", "quoted", TrustTier.OFFICIAL,
        )

    @staticmethod
    def _proposed(**overrides):
        base = {
            "assetType": "video", "field": "bitrateBps", "operator": "between",
            "value": [20_000_000, 30_000_000], "severity": "required",
            "confidence": "high",
        }
        base.update(overrides)
        return base

    def test_a_condition_on_a_measurable_property_is_accepted(self):
        rule = build_rule(
            self._proposed(appliesWhen={"heightPx": 1080}), self._evidence(), "r1"
        )
        assert rule.applies_when == {"heightPx": 1080}

    def test_a_condition_on_something_unmeasurable_is_rejected(self):
        """Silently unenforceable is worse than rejected.

        A condition Preflight cannot evaluate would scope the rule out of
        existence while still appearing in the pack as enforced.
        """
        with pytest.raises(RuleRejected, match="cannot measure"):
            build_rule(
                self._proposed(appliesWhen={"distributionTerritory": "EU"}),
                self._evidence(), "r1",
            )

    def test_a_malformed_condition_is_rejected(self):
        with pytest.raises(RuleRejected):
            build_rule(self._proposed(appliesWhen="1080p"), self._evidence(), "r1")

    def test_no_condition_means_unconditional(self):
        rule = build_rule(self._proposed(), self._evidence(), "r1")
        assert rule.applies_when == {}
