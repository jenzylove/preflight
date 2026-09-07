"""A delivery under the published floor must not be able to verify.

The failure this pins is not that a comparison returned the wrong answer. It is
that the comparison was never made: the requirement had been set aside, so a
212 kbit/s delivery satisfied a 320 kbit/s minimum by not being asked.

So these tests hold two things at once - that the floor blocks readiness when
it is not met, and that a rule is only ever set aside by its own identity, so
reviewing a bad extraction cannot quietly take a good sibling with it.
"""

from __future__ import annotations

from dataclasses import replace

from preflight_contracts.compare import evaluate_pack, is_ready
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

FLOOR_BPS = 320_000


def _evidence(eid: str, excerpt: str) -> SourceEvidence:
    return SourceEvidence(
        evidence_id=eid,
        url="https://artdocfest.com/en/content/technical-requirements/",
        retrieved_at="2026-08-25T00:00:00+00:00",
        source_hash=eid,
        quoted_excerpt=excerpt,
        trust_tier=TrustTier.OFFICIAL,
    )


def _rule(rule_id: str, operator: Operator, value, evidence_id: str) -> Rule:
    return Rule(
        rule_id=rule_id,
        asset_type=AssetType.AUDIO,
        field_name="bitrateBps",
        operator=operator,
        value=value,
        severity=Severity.REQUIRED,
        confidence=Confidence.HIGH,
        source_evidence_id=evidence_id,
    )


#: The correct reading: "Audio Bitrate: from 320 kbit/s".
FLOOR_RULE = _rule("r_floor", Operator.GTE, FLOOR_BPS, "ev_floor")
#: The misreading: the same figure on another page, with no operator at all.
EQUALITY_RULE = _rule("r_equality", Operator.EQ, FLOOR_BPS, "ev_equality")


def _pack(rules) -> RulePack:
    return RulePack(
        destination_id="artdocfest",
        version=1,
        rules=list(rules),
        evidence={
            "ev_floor": _evidence("ev_floor", "Audio Bitrate: from 320 kbit/s"),
            "ev_equality": _evidence("ev_equality", "Audio Data rate - 320 kbit/s"),
        },
    )


def _measured(bitrate: int) -> dict:
    return {"audio": {"bitrateBps": bitrate, "codec": "ac3", "sampleRateHz": 48000}}


def _ready(pack: RulePack, bitrate: int) -> bool:
    return is_ready(evaluate_pack(pack, _measured(bitrate), "artdocfest"))


class TestTheFloorGatesReadiness:
    def test_a_delivery_under_the_floor_is_not_ready(self):
        """212630 bps was shipped as VERIFIED against this exact requirement."""
        assert _ready(_pack([FLOOR_RULE]), 212_630) is False

    def test_a_delivery_exactly_on_the_floor_is_ready(self):
        assert _ready(_pack([FLOOR_RULE]), FLOOR_BPS) is True

    def test_a_delivery_above_the_floor_is_ready(self):
        """What the corrected repair now produces."""
        assert _ready(_pack([FLOOR_RULE]), 384_000) is True

    def test_the_floor_still_blocks_once_the_misreading_is_set_aside(self):
        """Setting the equality aside must not make the minimum disappear.

        This is the whole point: a package may verify with the misreading
        demoted, but only if it genuinely clears the published minimum.
        """
        # Setting a rule aside demotes it to context; it is never asserted.
        demoted = replace(EQUALITY_RULE, severity=Severity.CONTEXT)
        pack = _pack([FLOOR_RULE, demoted])
        assert _ready(pack, 212_630) is False
        assert _ready(pack, 384_000) is True

    def test_the_equality_alone_would_reject_the_corrected_encode(self):
        """Why the equality is a misreading and not merely inconvenient."""
        assert _ready(_pack([EQUALITY_RULE]), 384_000) is False
