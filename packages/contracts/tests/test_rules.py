"""The trust boundary is the thing worth testing hardest.

These tests encode the promises Preflight makes about what a model is allowed
to cause. They should be read as the specification, not as coverage.
"""

from __future__ import annotations

import pytest

from preflight_contracts.rules import (
    AssetType, Confidence, Operator, RulePack, RuleRejected, Severity,
    SourceEvidence, TrustTier, build_rule,
)


def evidence(tier: TrustTier = TrustTier.OFFICIAL, private: bool = False) -> SourceEvidence:
    return SourceEvidence(
        evidence_id="ev_1",
        url="" if private else "https://example.org/specs",
        retrieved_at="2026-08-09T00:00:00+00:00",
        source_hash="abc123",
        quoted_excerpt="Integrated loudness: -18... -21",
        trust_tier=tier,
        private=private,
    )


def proposed(**overrides) -> dict:
    base = {
        "assetType": "audio",
        "field": "integratedLoudnessLufs",
        "operator": "between",
        "value": [-21.0, -18.0],
        "severity": "required",
        "confidence": "high",
    }
    base.update(overrides)
    return base


class TestSourceTierEnforcement:
    def test_official_source_can_create_a_mandatory_rule(self):
        rule = build_rule(proposed(), evidence(TrustTier.OFFICIAL), "r1")
        assert rule.severity is Severity.REQUIRED

    def test_forum_source_cannot_create_a_mandatory_rule(self):
        # AC-2: a model insisting a requirement is mandatory does not make it so.
        rule = build_rule(proposed(), evidence(TrustTier.UNVERIFIED), "r1")
        assert rule.severity is Severity.CONTEXT

    def test_low_confidence_mandatory_claim_is_demoted(self):
        rule = build_rule(
            proposed(confidence="low"), evidence(TrustTier.OFFICIAL), "r1"
        )
        assert rule.severity is not Severity.REQUIRED


class TestSchemaRejection:
    def test_unknown_field_is_rejected(self):
        with pytest.raises(RuleRejected, match="not measurable"):
            build_rule(proposed(field="vibes"), evidence(), "r1")

    def test_field_from_the_wrong_asset_type_is_rejected(self):
        with pytest.raises(RuleRejected, match="not measurable"):
            build_rule(
                proposed(assetType="poster", field="integratedLoudnessLufs"),
                evidence(), "r1",
            )

    def test_unknown_operator_is_rejected(self):
        with pytest.raises(RuleRejected):
            build_rule(proposed(operator="approximately"), evidence(), "r1")

    def test_unknown_asset_type_is_rejected(self):
        with pytest.raises(RuleRejected):
            build_rule(proposed(assetType="hologram"), evidence(), "r1")

    def test_between_requires_two_ordered_bounds(self):
        with pytest.raises(RuleRejected, match="inverted"):
            build_rule(proposed(value=[-18.0, -21.0]), evidence(), "r1")
        with pytest.raises(RuleRejected, match="exactly"):
            build_rule(proposed(value=[-21.0]), evidence(), "r1")

    def test_numeric_operator_rejects_a_string(self):
        with pytest.raises(RuleRejected, match="requires a number"):
            build_rule(
                proposed(operator="gte", value="quite loud"), evidence(), "r1"
            )

    def test_in_operator_rejects_an_empty_list(self):
        with pytest.raises(RuleRejected):
            build_rule(proposed(operator="in", value=[]), evidence(), "r1")


class TestPrivacyBoundary:
    def test_private_specification_must_not_carry_a_public_url(self):
        with pytest.raises(RuleRejected, match="must not carry a public URL"):
            SourceEvidence(
                evidence_id="ev_p",
                url="https://example.org/leaked.pdf",
                retrieved_at="2026-08-09T00:00:00+00:00",
                source_hash="x",
                quoted_excerpt="confidential spec",
                trust_tier=TrustTier.PRIVATE_SPEC,
                private=True,
            )

    def test_evidence_without_an_excerpt_is_rejected(self):
        with pytest.raises(RuleRejected, match="quoted excerpt"):
            SourceEvidence(
                evidence_id="ev_2", url="https://example.org",
                retrieved_at="2026-08-09T00:00:00+00:00", source_hash="x",
                quoted_excerpt="   ", trust_tier=TrustTier.OFFICIAL,
            )


class TestDigestStability:
    def test_equivalent_packs_produce_the_same_digest(self):
        def make() -> RulePack:
            ev = evidence()
            return RulePack(
                destination_id="d", version=1, evidence={"ev_1": ev},
                rules=[build_rule(proposed(), ev, "r1")],
            )

        assert make().digest() == make().digest()

    def test_rule_order_does_not_change_the_pack_digest(self):
        ev = evidence()
        a = build_rule(proposed(), ev, "r1")
        b = build_rule(proposed(field="sampleRateHz", operator="eq", value=48000), ev, "r2")
        forward = RulePack("d", 1, [a, b], {"ev_1": ev})
        reverse = RulePack("d", 1, [b, a], {"ev_1": ev})
        assert forward.digest() == reverse.digest()

    def test_changing_a_value_changes_the_digest(self):
        ev = evidence()
        original = RulePack("d", 1, [build_rule(proposed(), ev, "r1")], {"ev_1": ev})
        altered = RulePack(
            "d", 1, [build_rule(proposed(value=[-24.0, -22.0]), ev, "r1")], {"ev_1": ev}
        )
        assert original.digest() != altered.digest()
