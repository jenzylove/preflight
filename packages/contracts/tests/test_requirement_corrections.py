from preflight_contracts.requirement_corrections import is_dcp_only_isdcf_rule
from preflight_contracts.rules import (
    AssetType,
    Confidence,
    Operator,
    Rule,
    SourceEvidence,
    Severity,
    TrustTier,
)


def _rule() -> Rule:
    return Rule(
        rule_id="r-isdcf",
        asset_type=AssetType.PACKAGE,
        field_name="fileNamePattern",
        operator=Operator.EQ,
        value="ISDCF",
        severity=Severity.REQUIRED,
        source_evidence_id="ev-isdcf",
        confidence=Confidence.HIGH,
    )


def _evidence(excerpt: str) -> SourceEvidence:
    return SourceEvidence(
        evidence_id="ev-isdcf",
        url="https://www.sundance.org/spec.pdf",
        retrieved_at="2026-01-01T00:00:00+00:00",
        source_hash="a" * 64,
        quoted_excerpt=excerpt,
        trust_tier=TrustTier.OFFICIAL,
    )


def test_isdcf_scoped_to_dcp_is_held_for_review():
    assert is_dcp_only_isdcf_rule(
        _rule(),
        _evidence("DCPs must comply with ISDCF naming conventions."),
    )


def test_isdcf_online_filename_requirement_is_not_reclassified():
    assert not is_dcp_only_isdcf_rule(
        _rule(),
        _evidence("Online screening files must use ISDCF naming conventions."),
    )
