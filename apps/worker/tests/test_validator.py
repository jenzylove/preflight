from preflight_contracts.compare import Assertion, Result
from preflight_contracts.rules import (
    AssetType,
    Confidence,
    Operator,
    Rule,
    RulePack,
    Severity,
    SourceEvidence,
    TrustTier,
)
from preflight_worker.validate import source_rule_conflicts


def test_sundance_lt_bitrate_conflict_is_recorded_from_source_evidence():
    rule = Rule(
        rule_id="bitrate",
        asset_type=AssetType.VIDEO,
        field_name="bitrateBps",
        operator=Operator.BETWEEN,
        value=[82_000_000, 102_000_000],
        severity=Severity.REQUIRED,
        source_evidence_id="sundance",
        confidence=Confidence.HIGH,
    )
    pack = RulePack(
        destination_id="sundance-film-festival",
        version=1,
        rules=[rule],
        evidence={
            "sundance": SourceEvidence(
                evidence_id="sundance",
                url="https://www.sundance.org/spec.pdf",
                retrieved_at="2026-01-01T00:00:00+00:00",
                source_hash="a" * 64,
                quoted_excerpt=(
                    "Image Bit rate 82–102 Mbps (as set automatically by LT codec)"
                ),
                trust_tier=TrustTier.OFFICIAL,
            )
        },
    )
    assertion = Assertion(
        rule_id="bitrate",
        destination_id="sundance-film-festival",
        asset_type=AssetType.VIDEO,
        field_name="bitrateBps",
        expected="between 82000000 and 102000000",
        measured=39_125_558,
        result=Result.REVIEW_REQUIRED,
        severity=Severity.REQUIRED,
        source_evidence_id="sundance",
    )

    conflicts = source_rule_conflicts(
        pack,
        [assertion],
        {AssetType.VIDEO: {"codec": "prores", "profile": "LT", "bitrateBps": 39_125_558}},
    )

    assert len(conflicts) == 1
    assert "source/toolchain conflict" in conflicts[0]
    assert "39125558 bps" in conflicts[0]
