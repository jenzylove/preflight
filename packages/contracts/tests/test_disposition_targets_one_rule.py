"""Setting one requirement aside must not take its siblings with it.

Artdocfest publishes the audio data rate on two pages. One was extracted
correctly as a floor, the other as an exact equality. Both are
``audio.bitrateBps``, and the acceptance helper selected rules by asset type
and field, so reviewing the bad reading silently dismissed the good one. The
delivery then verified against a minimum nobody was checking.

The product surface always dispositioned a single rule id, so the defect lived
entirely in the helpers - which is exactly the kind of thing that only shows up
when someone reads the resulting passport line by line.
"""

from __future__ import annotations

import importlib.util
from dataclasses import replace
from pathlib import Path

import pytest
from preflight_contracts.rules import (
    AssetType,
    Confidence,
    Operator,
    Rule,
    Severity,
)

ROOT = Path(__file__).resolve().parents[3]


def _load_e2e():
    """Load scripts/e2e_verified.py without running it."""
    path = ROOT / "scripts" / "e2e_verified.py"
    spec = importlib.util.spec_from_file_location("e2e_verified", path)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def _api_rule(field, operator, expected, severity="required", asset_type="audio"):
    """The shape the API returns from /v1/projects/{id}/rules."""
    return {
        "rule_id": f"{asset_type}.{field}.{operator}.{expected}",
        "asset_type": asset_type,
        "field": field,
        "operator": operator,
        "expected": expected,
        "severity": severity,
        "confidence": "high",
        "destination": "artdocfest",
    }


FLOOR = _api_rule("bitrateBps", "gte", "320000")
EQUALITY = _api_rule("bitrateBps", "eq", "320000")
BUSAN_RANGE = _api_rule("bitrateBps", "between", "[128000.0, 320000.0]", severity="context")
TRUE_PEAK_EQ = _api_rule("truePeakDbtp", "eq", "-3")
TRUE_PEAK_CEILING = _api_rule("truePeakDbtp", "lte", "-3")
LOUDNESS_RANGE = _api_rule("loudnessRangeLu", "between", "[25.0, 30.0]")
NAME_PATTERN = _api_rule("fileNamePattern", "eq", "ISDCF", asset_type="package")


class TestTheHelperSelectsOneRuleNotAField:
    @pytest.fixture(scope="class")
    def e2e(self):
        return _load_e2e()

    def test_the_published_floor_is_never_set_aside(self, e2e):
        """The exact regression. This returned True and broke verification."""
        assert e2e.is_misread(FLOOR) is False

    def test_the_equality_misreading_is_still_caught(self, e2e):
        assert e2e.is_misread(EQUALITY) is True

    def test_the_floor_and_the_equality_share_a_field(self):
        """If they did not, the bug could not have happened."""
        assert (FLOOR["asset_type"], FLOOR["field"]) == \
               (EQUALITY["asset_type"], EQUALITY["field"])

    def test_the_true_peak_ceiling_survives_its_misread_sibling(self, e2e):
        """'-3 (Peak)' as a ceiling is correct; as an equality it is not."""
        assert e2e.is_misread(TRUE_PEAK_EQ) is True
        assert e2e.is_misread(TRUE_PEAK_CEILING) is False

    def test_context_only_rules_are_left_alone(self, e2e):
        """A context rule is never asserted, so setting it aside is only noise."""
        assert e2e.is_misread(BUSAN_RANGE) is False

    def test_the_genuine_misreadings_are_still_selected(self, e2e):
        assert e2e.is_misread(LOUDNESS_RANGE) is True
        assert e2e.is_misread(NAME_PATTERN) is True

    def test_every_selected_rule_has_a_stated_reason(self, e2e):
        """The reason is mandatory and ends up printed on the passport."""
        for rule in (EQUALITY, TRUE_PEAK_EQ, LOUDNESS_RANGE, NAME_PATTERN):
            assert len(e2e.reason_for(rule).strip()) > 40

    def test_the_keep_list_names_the_floor(self, e2e):
        assert ("audio", "bitrateBps", "gte") in e2e.MUST_STAY_IN_FORCE


class TestDispositionIsKeyedByRuleIdentity:
    """The contract layer demotes exactly the rules it was given, and no others."""

    def _rule(self, rule_id: str, operator: Operator, value) -> Rule:
        return Rule(
            rule_id=rule_id,
            asset_type=AssetType.AUDIO,
            field_name="bitrateBps",
            operator=operator,
            value=value,
            severity=Severity.REQUIRED,
            confidence=Confidence.HIGH,
            source_evidence_id="ev",
        )

    def test_demoting_one_rule_leaves_its_sibling_required(self):
        floor = self._rule("r_floor", Operator.GTE, 320_000)
        equality = self._rule("r_equality", Operator.EQ, 320_000)

        set_aside = {"r_equality"}
        result = [
            replace(r, severity=Severity.CONTEXT) if r.rule_id in set_aside else r
            for r in (floor, equality)
        ]

        by_id = {r.rule_id: r for r in result}
        assert by_id["r_equality"].severity is Severity.CONTEXT
        assert by_id["r_floor"].severity is Severity.REQUIRED

    def test_matching_on_field_would_have_demoted_both(self):
        """Documents the defect this file exists to prevent returning."""
        floor = self._rule("r_floor", Operator.GTE, 320_000)
        equality = self._rule("r_equality", Operator.EQ, 320_000)

        by_field = {(r.asset_type, r.field_name) for r in (equality,)}
        swept = [r for r in (floor, equality) if (r.asset_type, r.field_name) in by_field]
        assert len(swept) == 2, "selecting by field takes the valid rule too"
