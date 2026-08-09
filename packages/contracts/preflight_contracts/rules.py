"""Strict rule contract.

This module is the trust boundary. A language model proposes rules; nothing
here trusts it. Every field, operator and severity is validated against a
closed vocabulary, and severity is *re-derived from the source tier in Python*
after the model returns, so no model output can promote a weak source into a
mandatory requirement.
"""

from __future__ import annotations

import hashlib
import json
from dataclasses import dataclass, field, asdict
from enum import Enum
from typing import Any


SCHEMA_VERSION = "1.0.0"


class TrustTier(str, Enum):
    """Where a requirement came from, and therefore how far it can be trusted."""

    OFFICIAL = "A"          # destination's own published documentation
    PRIVATE_SPEC = "B"      # specification the user uploaded, confirmed by them
    REFERENCED_STD = "C"    # industry standard the destination explicitly cites
    UNVERIFIED = "D"        # blog, forum, aggregator, search snippet

    @property
    def may_create_mandatory_rule(self) -> bool:
        return self in (TrustTier.OFFICIAL, TrustTier.PRIVATE_SPEC, TrustTier.REFERENCED_STD)


class Severity(str, Enum):
    REQUIRED = "required"
    RECOMMENDED = "recommended"
    CONTEXT = "context"     # retained for the user to read, never asserted against a file


class Confidence(str, Enum):
    HIGH = "high"
    MEDIUM = "medium"
    LOW = "low"


class Operator(str, Enum):
    EQ = "eq"
    NEQ = "neq"
    GTE = "gte"
    LTE = "lte"
    BETWEEN = "between"     # value is [lo, hi], inclusive
    IN = "in"               # value is a list of acceptable values
    NOT_IN = "not_in"
    PRESENT = "present"     # the field must exist and be non-empty
    ABSENT = "absent"


class AssetType(str, Enum):
    VIDEO = "video"
    AUDIO = "audio"
    SUBTITLE = "subtitle"
    POSTER = "poster"
    METADATA = "metadata"
    PACKAGE = "package"


#: Closed vocabulary of measurable properties. A rule naming a field outside
#: this set is rejected — we will not assert a requirement we cannot measure.
MEASURABLE_FIELDS: dict[AssetType, set[str]] = {
    AssetType.VIDEO: {
        "container", "codec", "profile", "widthPx", "heightPx", "frameRate",
        "displayAspectRatio", "bitrateBps", "colourPrimaries", "colourTransfer",
        "colourMatrix", "scanType", "fastStart", "durationSeconds",
    },
    AssetType.AUDIO: {
        "codec", "channels", "sampleRateHz", "bitrateBps",
        "integratedLoudnessLufs", "truePeakDbtp", "loudnessRangeLu",
    },
    AssetType.SUBTITLE: {"format", "encoding", "cueCount", "burnedIn", "language"},
    AssetType.POSTER: {"format", "widthPx", "heightPx", "aspectRatio", "colourSpace", "byteSize"},
    AssetType.METADATA: {"title", "synopsisChars", "language", "runtimeSeconds", "countryOfOrigin"},
    AssetType.PACKAGE: {"fileNamePattern", "folderLayout", "checksumAlgorithm"},
}


class RuleRejected(ValueError):
    """Raised when proposed rule data does not satisfy the contract."""


@dataclass(frozen=True)
class SourceEvidence:
    """Proof of where a requirement was published."""

    evidence_id: str
    url: str
    retrieved_at: str          # ISO 8601 UTC
    source_hash: str           # sha256 of the retrieved text, for drift detection
    quoted_excerpt: str
    trust_tier: TrustTier
    private: bool = False

    def __post_init__(self) -> None:
        if not self.quoted_excerpt.strip():
            raise RuleRejected(f"{self.evidence_id}: evidence must carry a quoted excerpt")
        if self.private and self.url:
            raise RuleRejected(f"{self.evidence_id}: private specifications must not carry a public URL")


@dataclass(frozen=True)
class Rule:
    """One checkable requirement, bound to the evidence that published it."""

    rule_id: str
    asset_type: AssetType
    field_name: str
    operator: Operator
    value: Any
    severity: Severity
    source_evidence_id: str
    confidence: Confidence
    note: str = ""

    def digest(self) -> str:
        payload = json.dumps(
            {
                "assetType": self.asset_type.value,
                "field": self.field_name,
                "operator": self.operator.value,
                "value": self.value,
                "severity": self.severity.value,
            },
            sort_keys=True,
            separators=(",", ":"),
        )
        return hashlib.sha256(payload.encode()).hexdigest()[:16]


def _validate_value(operator: Operator, value: Any) -> None:
    if operator in (Operator.PRESENT, Operator.ABSENT):
        if value not in (None, True):
            raise RuleRejected(f"operator {operator.value} takes no value, got {value!r}")
        return
    if operator is Operator.BETWEEN:
        if not (isinstance(value, (list, tuple)) and len(value) == 2):
            raise RuleRejected("operator 'between' requires exactly [lo, hi]")
        lo, hi = value
        if not all(isinstance(v, (int, float)) for v in (lo, hi)):
            raise RuleRejected("operator 'between' requires numeric bounds")
        if lo > hi:
            raise RuleRejected(f"operator 'between' bounds inverted: [{lo}, {hi}]")
        return
    if operator in (Operator.IN, Operator.NOT_IN):
        if not isinstance(value, (list, tuple)) or not value:
            raise RuleRejected(f"operator {operator.value} requires a non-empty list")
        return
    if operator in (Operator.GTE, Operator.LTE):
        if not isinstance(value, (int, float)):
            raise RuleRejected(f"operator {operator.value} requires a number, got {type(value).__name__}")
        return
    if value is None:
        raise RuleRejected(f"operator {operator.value} requires a value")


def build_rule(proposed: dict[str, Any], evidence: SourceEvidence, rule_id: str) -> Rule:
    """Turn untrusted model output into a Rule, or refuse.

    Severity is never taken from the model. It is derived from the trust tier of
    the evidence, so a requirement quoted from a forum post cannot become
    mandatory no matter what the model claims about it.
    """
    try:
        asset_type = AssetType(proposed["assetType"])
        operator = Operator(proposed["operator"])
    except (KeyError, ValueError) as exc:
        raise RuleRejected(f"unknown assetType or operator: {exc}") from exc

    field_name = proposed.get("field", "")
    if field_name not in MEASURABLE_FIELDS[asset_type]:
        raise RuleRejected(
            f"field {field_name!r} is not measurable for {asset_type.value}; "
            "Preflight does not assert requirements it cannot verify"
        )

    value = proposed.get("value")
    _validate_value(operator, value)

    try:
        confidence = Confidence(proposed.get("confidence", "low"))
    except ValueError as exc:
        raise RuleRejected(f"unknown confidence: {exc}") from exc

    claimed = proposed.get("severity", "context")
    try:
        claimed_severity = Severity(claimed)
    except ValueError as exc:
        raise RuleRejected(f"unknown severity: {exc}") from exc

    severity = _derive_severity(claimed_severity, evidence.trust_tier, confidence)

    return Rule(
        rule_id=rule_id,
        asset_type=asset_type,
        field_name=field_name,
        operator=operator,
        value=list(value) if isinstance(value, tuple) else value,
        severity=severity,
        source_evidence_id=evidence.evidence_id,
        confidence=confidence,
        note=str(proposed.get("note", ""))[:500],
    )


def _derive_severity(claimed: Severity, tier: TrustTier, confidence: Confidence) -> Severity:
    """Severity is a property of the source, not of the model's opinion."""
    if not tier.may_create_mandatory_rule:
        return Severity.CONTEXT
    if claimed is Severity.REQUIRED and confidence is Confidence.LOW:
        # A mandatory claim the model is unsure of blocks readiness rather than
        # driving it. Surfaced to the user for confirmation instead.
        return Severity.RECOMMENDED
    return claimed


@dataclass
class RulePack:
    """A versioned, citation-backed set of requirements for one destination."""

    destination_id: str
    version: int
    rules: list[Rule] = field(default_factory=list)
    evidence: dict[str, SourceEvidence] = field(default_factory=dict)
    schema_version: str = SCHEMA_VERSION

    def digest(self) -> str:
        payload = "|".join(sorted(r.digest() for r in self.rules))
        return hashlib.sha256(f"{self.destination_id}:{payload}".encode()).hexdigest()[:16]

    def required_rules(self) -> list[Rule]:
        return [r for r in self.rules if r.severity is Severity.REQUIRED]

    def to_json(self) -> str:
        return json.dumps(
            {
                "destinationId": self.destination_id,
                "version": self.version,
                "schemaVersion": self.schema_version,
                "digest": self.digest(),
                "rules": [asdict(r) for r in self.rules],
                "evidence": [asdict(e) for e in self.evidence.values()],
            },
            indent=2,
            default=str,
        )
