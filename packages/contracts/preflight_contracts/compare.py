"""Deterministic compatibility engine.

No language model participates in this file. Given measured properties and a
rule pack, the same inputs always produce the same assertions and the same
digest. This is what makes a Preflight result something a user can check rather
than something they have to believe.
"""

from __future__ import annotations

import hashlib
import json
from dataclasses import dataclass
from enum import Enum
from typing import Any

from .rules import AssetType, Confidence, Operator, Rule, RulePack, Severity


class Result(str, Enum):
    PASS = "PASS"
    REPAIRABLE = "REPAIRABLE"              # fails, but a green operation fixes it
    REVIEW_REQUIRED = "REVIEW_REQUIRED"    # fails, only a yellow operation fixes it
    UNSUPPORTED = "UNSUPPORTED"            # fails, needs work Preflight will not do
    AMBIGUOUS = "AMBIGUOUS"                # sources disagree, or confidence too low
    NOT_MEASURED = "NOT_MEASURED"          # the property was never measured
    NOT_APPLICABLE = "NOT_APPLICABLE"      # conditional rule, out of scope for this asset


#: Which failures a green (deterministic, non-creative) repair can resolve.
GREEN_REPAIRABLE: dict[tuple[AssetType, str], str] = {
    (AssetType.AUDIO, "integratedLoudnessLufs"): "normalise_loudness",
    (AssetType.AUDIO, "truePeakDbtp"): "normalise_loudness",
    (AssetType.VIDEO, "displayAspectRatio"): "rewrite_container_metadata",
    (AssetType.VIDEO, "fastStart"): "rewrite_container_metadata",
    (AssetType.VIDEO, "colourPrimaries"): "rewrite_container_metadata",
    (AssetType.VIDEO, "colourTransfer"): "rewrite_container_metadata",
    (AssetType.VIDEO, "colourMatrix"): "rewrite_container_metadata",
    (AssetType.POSTER, "widthPx"): "resize_poster",
    (AssetType.POSTER, "heightPx"): "resize_poster",
    (AssetType.POSTER, "format"): "resize_poster",
    (AssetType.SUBTITLE, "format"): "convert_subtitles",
    (AssetType.METADATA, "synopsisChars"): "normalise_metadata",
    (AssetType.METADATA, "title"): "normalise_metadata",
    (AssetType.PACKAGE, "fileNamePattern"): "rename_and_layout",
    (AssetType.PACKAGE, "folderLayout"): "rename_and_layout",
    (AssetType.PACKAGE, "checksumAlgorithm"): "build_manifest",
}

#: Failures that require re-encoding the picture. Real, but not green: they can
#: change quality, so Preflight reports them and refuses to do them silently.
YELLOW_FIELDS: set[tuple[AssetType, str]] = {
    (AssetType.VIDEO, "bitrateBps"),
    (AssetType.VIDEO, "widthPx"),
    (AssetType.VIDEO, "heightPx"),
    (AssetType.VIDEO, "codec"),
    (AssetType.VIDEO, "profile"),
    (AssetType.VIDEO, "frameRate"),
    (AssetType.VIDEO, "container"),
    (AssetType.AUDIO, "codec"),
    (AssetType.AUDIO, "sampleRateHz"),
    (AssetType.AUDIO, "bitrateBps"),
    (AssetType.AUDIO, "channels"),
}


@dataclass(frozen=True)
class Assertion:
    rule_id: str
    destination_id: str
    asset_type: AssetType
    field_name: str
    expected: str
    measured: Any
    result: Result
    severity: Severity
    source_evidence_id: str
    repair_operation: str | None = None
    explanation: str = ""


def _describe(rule: Rule) -> str:
    op, val = rule.operator, rule.value
    if op is Operator.BETWEEN:
        return f"between {val[0]} and {val[1]}"
    if op is Operator.ANY_OF_RANGES:
        return "any of " + " or ".join(f"{lo}-{hi}" for lo, hi in val)
    if op is Operator.IN:
        return "one of " + ", ".join(str(v) for v in val)
    if op is Operator.NOT_IN:
        return "not one of " + ", ".join(str(v) for v in val)
    if op is Operator.PRESENT:
        return "present"
    if op is Operator.ABSENT:
        return "absent"
    return f"{op.value} {val}"


def _satisfied(rule: Rule, measured: Any) -> bool:
    op, expected = rule.operator, rule.value

    if op is Operator.PRESENT:
        return measured not in (None, "", [], {})
    if op is Operator.ABSENT:
        return measured in (None, "", [], {}, False)

    if measured is None:
        return False

    if op is Operator.EQ:
        return _norm(measured) == _norm(expected)
    if op is Operator.NEQ:
        return _norm(measured) != _norm(expected)
    if op is Operator.GTE:
        return float(measured) >= float(expected)
    if op is Operator.LTE:
        return float(measured) <= float(expected)
    if op is Operator.BETWEEN:
        return float(expected[0]) <= float(measured) <= float(expected[1])
    if op is Operator.ANY_OF_RANGES:
        return any(float(lo) <= float(measured) <= float(hi) for lo, hi in expected)
    if op is Operator.IN:
        return _norm(measured) in {_norm(v) for v in expected}
    if op is Operator.NOT_IN:
        return _norm(measured) not in {_norm(v) for v in expected}
    return False


def _norm(value: Any) -> Any:
    """Normalise for comparison so 'H.264', 'h264' and 'AVC' do not disagree."""
    if isinstance(value, str):
        cleaned = value.strip().lower().replace("-", "").replace(".", "").replace("_", "")
        aliases = {
            "avc": "h264", "avc1": "h264", "mpeg4avc": "h264",
            "aaclc": "aac", "mp4a": "aac", "ac3": "ac3",
            "subrip": "srt", "webvtt": "vtt",
            "jpg": "jpeg",
            "bt709": "bt709", "rec709": "bt709", "itur bt709": "bt709",
        }
        return aliases.get(cleaned, cleaned)
    if isinstance(value, float) and value.is_integer():
        return int(value)
    return value


def evaluate(
    rule: Rule,
    measured_properties: dict[str, Any],
    destination_id: str,
    ambiguous_rule_ids: frozenset[str] = frozenset(),
) -> Assertion:
    """Compare one rule against measured evidence."""
    key = (rule.asset_type, rule.field_name)
    measured = measured_properties.get(rule.field_name)
    expected = _describe(rule)

    def build(result: Result, operation: str | None = None, why: str = "") -> Assertion:
        return Assertion(
            rule_id=rule.rule_id,
            destination_id=destination_id,
            asset_type=rule.asset_type,
            field_name=rule.field_name,
            expected=expected,
            measured=measured,
            result=result,
            severity=rule.severity,
            source_evidence_id=rule.source_evidence_id,
            repair_operation=operation,
            explanation=why,
        )

    if rule.applies_when and not rule.applies_to(measured_properties):
        scope = ", ".join(f"{k}={v}" for k, v in rule.applies_when.items())
        return build(
            Result.NOT_APPLICABLE,
            why=f"This requirement applies only when {scope}.",
        )

    if rule.rule_id in ambiguous_rule_ids:
        return build(Result.AMBIGUOUS, why="Official sources disagree on this requirement.")

    if rule.confidence is Confidence.LOW and rule.severity is Severity.REQUIRED:
        return build(Result.AMBIGUOUS, why="Requirement could not be read with confidence.")

    if measured is None and rule.operator not in (Operator.ABSENT,):
        return build(
            Result.NOT_MEASURED,
            why="This property was not measured on the supplied assets.",
        )

    if _satisfied(rule, measured):
        return build(Result.PASS)

    if key in GREEN_REPAIRABLE:
        op = GREEN_REPAIRABLE[key]
        return build(Result.REPAIRABLE, op, f"Correctable without re-encoding the picture ({op}).")

    if key in YELLOW_FIELDS:
        return build(
            Result.REVIEW_REQUIRED,
            why="Correcting this re-encodes the picture and can change quality. "
                "Needs your decision.",
        )

    return build(Result.UNSUPPORTED, why="No supported operation can satisfy this requirement.")


def evaluate_pack(
    pack: RulePack,
    measured_by_asset_type: dict[AssetType, dict[str, Any]],
    ambiguous_rule_ids: frozenset[str] = frozenset(),
) -> list[Assertion]:
    return [
        evaluate(
            rule,
            measured_by_asset_type.get(rule.asset_type, {}),
            pack.destination_id,
            ambiguous_rule_ids,
        )
        for rule in pack.rules
    ]


def is_ready(assertions: list[Assertion]) -> bool:
    """Readiness is derived, never set. Any required rule that is not PASS blocks."""
    return all(
        a.result is Result.PASS
        for a in assertions
        if a.severity is Severity.REQUIRED
    )


def comparison_digest(assertions: list[Assertion]) -> str:
    """Stable across runs for equivalent inputs — the proof of determinism."""
    payload = json.dumps(
        sorted(
            [
                f"{a.destination_id}:{a.rule_id}:{a.result.value}:{_norm(a.measured)}"
                for a in assertions
            ]
        ),
        separators=(",", ":"),
    )
    return hashlib.sha256(payload.encode()).hexdigest()[:16]


class ConflictStrength(str, Enum):
    """How binding a cross-destination conflict is.

    The distinction matters to the user. HARD means no single file can be
    delivered to both, full stop. SOFT means one destination merely recommends
    what the other mandates — the user can legitimately ship one file and accept
    a suboptimal result at the recommending destination. Collapsing the two
    would either overstate the problem or hide it.
    """

    HARD = "hard"   # required vs required — genuinely impossible
    SOFT = "soft"   # a recommendation collides with a mandate — a real choice


def find_conflicts(packs: list[RulePack]) -> list[dict[str, Any]]:
    """Detect requirements that no single asset can satisfy across destinations.

    This is the finding that justifies the product: not 'your file is wrong',
    but 'these destinations want incompatible things, and here is each one's
    own published sentence saying so'.
    """
    conflicts: list[dict[str, Any]] = []
    by_field: dict[tuple[AssetType, str], list[tuple[RulePack, Rule]]] = {}

    for pack in packs:
        for rule in pack.rules:
            if rule.severity is Severity.CONTEXT:
                continue  # context is never asserted, so it can never conflict
            by_field.setdefault((rule.asset_type, rule.field_name), []).append((pack, rule))

    for (asset_type, field_name), entries in by_field.items():
        if len(entries) < 2:
            continue
        for i in range(len(entries)):
            for j in range(i + 1, len(entries)):
                (pack_a, rule_a), (pack_b, rule_b) = entries[i], entries[j]
                if pack_a.destination_id == pack_b.destination_id:
                    continue
                if not _mutually_exclusive(rule_a, rule_b):
                    continue
                both_required = (
                    rule_a.severity is Severity.REQUIRED
                    and rule_b.severity is Severity.REQUIRED
                )
                conflicts.append({
                    "assetType": asset_type.value,
                    "field": field_name,
                    "strength": (
                        ConflictStrength.HARD if both_required else ConflictStrength.SOFT
                    ).value,
                    "destinations": [pack_a.destination_id, pack_b.destination_id],
                    "requirements": [_describe(rule_a), _describe(rule_b)],
                    "severities": [rule_a.severity.value, rule_b.severity.value],
                    "evidence": [rule_a.source_evidence_id, rule_b.source_evidence_id],
                    "resolution": "separate_derived_assets",
                })

    # Hard conflicts first — they are decisions the user cannot avoid.
    conflicts.sort(key=lambda c: (c["strength"] != ConflictStrength.HARD.value, c["field"]))
    return conflicts


def _mutually_exclusive(a: Rule, b: Rule) -> bool:
    """True when no single value can satisfy both rules.

    Rules scoped to different conditions never conflict: '20-30 Mbps at
    FullHD' and '90-120 Mbps at 4K' are two requirements, not a contradiction.
    """
    if a.condition_key() != b.condition_key():
        return False

    ra, rb = _numeric_range(a), _numeric_range(b)
    if ra and rb:
        return ra[1] < rb[0] or rb[1] < ra[0]

    if a.operator is Operator.IN and b.operator is Operator.IN:
        return not ({_norm(v) for v in a.value} & {_norm(v) for v in b.value})
    if a.operator is Operator.EQ and b.operator is Operator.EQ:
        return _norm(a.value) != _norm(b.value)
    return False


#: Public names for the two predicates the agent's reconciliation needs. Kept
#: as thin aliases so there is exactly one implementation of "what does this
#: rule say" and "can these two rules both hold".
describe_rule = _describe
mutually_exclusive = _mutually_exclusive


def _numeric_range(rule: Rule) -> tuple[float, float] | None:
    inf = float("inf")
    if rule.operator is Operator.ANY_OF_RANGES:
        # The span the rule permits overall. Two alternative-tier rules only
        # conflict if their whole spans are disjoint.
        lows = [float(w[0]) for w in rule.value]
        highs = [float(w[1]) for w in rule.value]
        return min(lows), max(highs)
    if rule.operator is Operator.BETWEEN:
        return float(rule.value[0]), float(rule.value[1])
    if rule.operator is Operator.GTE:
        return float(rule.value), inf
    if rule.operator is Operator.LTE:
        return -inf, float(rule.value)
    if rule.operator is Operator.EQ and isinstance(rule.value, (int, float)):
        return float(rule.value), float(rule.value)
    return None


def rules_equivalent(a: Rule, b: Rule) -> bool:
    """Whether two rules impose the same requirement, however they are worded.

    'eq mp4' and 'one of [mp4]' are the same requirement. So are 'between
    20 and 30' and a pair of gte/lte bounds. Treating those as disagreements
    made extraction look wrong when it was right, which is the worst kind of
    metric: one that punishes correct behaviour.
    """
    if a.asset_type is not b.asset_type or a.field_name != b.field_name:
        return False

    a_set, b_set = _acceptable_set(a), _acceptable_set(b)
    if a_set is not None and b_set is not None:
        return a_set == b_set

    a_range, b_range = _numeric_range(a), _numeric_range(b)
    if a_range and b_range:
        return a_range == b_range

    if a.operator is b.operator:
        return _norm(a.value) == _norm(b.value)
    return False


def _acceptable_set(rule: Rule) -> set | None:
    """The set of values a rule admits, when it admits a finite set."""
    if rule.operator is Operator.EQ:
        return {_norm(rule.value)}
    if rule.operator is Operator.IN:
        return {_norm(v) for v in rule.value}
    return None
