"""Rule pack storage and user confirmation.

Gate 3 established that extraction gets roughly two values in three exactly
right. That is useful and not sufficient, which makes this module the thing
that keeps the rest honest: a rule the model was unsure about, or that official
sources state inconsistently, does not become a requirement until a human
looks at it next to its own source and says yes.

Confirmation is per-rule and recorded. 'The user confirmed it' is part of the
provenance chain, not a flag that erases where the rule came from.
"""

from __future__ import annotations

import uuid

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
from sqlalchemy import select
from sqlalchemy.orm import Session

from ..core.models import Destination, RulePackRow, RuleRow, SourceEvidenceRow

#: Statuses a rule pack moves through. Only CONFIRMED packs are ever compared
#: against a film.
DRAFT = "DRAFT"
CONFIRMED = "CONFIRMED"
SUPERSEDED = "SUPERSEDED"


def _to_contract_rule(row: RuleRow) -> Rule:
    return Rule(
        rule_id=str(row.id),
        asset_type=AssetType(row.asset_type),
        field_name=row.field,
        operator=Operator(row.operator),
        value=(row.expected_value_json or {}).get("value")
        if isinstance(row.expected_value_json, dict) else row.expected_value_json,
        severity=Severity(row.severity),
        source_evidence_id=str(row.source_evidence_id),
        confidence=Confidence(row.confidence),
        note=row.note or "",
        applies_when=(row.expected_value_json or {}).get("appliesWhen", {})
        if isinstance(row.expected_value_json, dict) else {},
    )


def _to_contract_evidence(row: SourceEvidenceRow) -> SourceEvidence:
    return SourceEvidence(
        evidence_id=str(row.id),
        url=row.url or "",
        retrieved_at=row.retrieved_at.isoformat(),
        source_hash=row.source_hash,
        quoted_excerpt=row.quoted_excerpt,
        trust_tier=TrustTier(row.trust_tier),
        private=row.private,
    )


def load_project_rule_packs(
    project_id: uuid.UUID, session: Session
) -> tuple[list[RulePack], dict[str, SourceEvidence], set[str]]:
    """Load the confirmed rule packs a project will be measured against.

    Returns the packs, an evidence lookup so every assertion can show its
    source, and the ids of rules still awaiting confirmation — those become
    AMBIGUOUS rather than silently applying.
    """
    from ..core.models import Project

    project = session.get(Project, project_id)
    if project is None:
        return [], {}, set()

    pack_rows = session.scalars(
        select(RulePackRow)
        .where(RulePackRow.status == CONFIRMED)
        .order_by(RulePackRow.created_at.desc())
    ).all()

    packs: list[RulePack] = []
    evidence_lookup: dict[str, SourceEvidence] = {}
    unconfirmed: set[str] = set()

    seen_destinations: set[uuid.UUID] = set()
    for pack_row in pack_rows:
        if pack_row.destination_id in seen_destinations:
            continue   # newest confirmed version per destination wins
        seen_destinations.add(pack_row.destination_id)

        destination = session.get(Destination, pack_row.destination_id)
        if destination is None:
            continue

        rule_rows = session.scalars(
            select(RuleRow).where(RuleRow.rule_pack_id == pack_row.id)
        ).all()

        rules: list[Rule] = []
        evidence: dict[str, SourceEvidence] = {}
        for rule_row in rule_rows:
            evidence_row = session.get(SourceEvidenceRow, rule_row.source_evidence_id)
            if evidence_row is None:
                continue
            contract_evidence = _to_contract_evidence(evidence_row)
            evidence[contract_evidence.evidence_id] = contract_evidence
            evidence_lookup[contract_evidence.evidence_id] = contract_evidence

            rule = _to_contract_rule(rule_row)
            rules.append(rule)

            if _needs_confirmation(rule_row):
                unconfirmed.add(rule.rule_id)

        packs.append(RulePack(
            destination_id=destination.slug,
            version=pack_row.version,
            rules=rules,
            evidence=evidence,
        ))

    return packs, evidence_lookup, unconfirmed


def _needs_confirmation(row: RuleRow) -> bool:
    """A mandatory rule the model was unsure of is not yet a requirement."""
    return row.severity == Severity.REQUIRED.value and row.confidence != Confidence.HIGH.value


def rules_awaiting_confirmation(
    session: Session, rule_pack_id: uuid.UUID
) -> list[dict]:
    """Everything a user must look at before this pack can be trusted.

    Each entry carries the source URL and the quoted sentence, so the decision
    is 'does this match what the page says', not 'do you trust the machine'.
    """
    rows = session.scalars(
        select(RuleRow).where(RuleRow.rule_pack_id == rule_pack_id)
    ).all()

    pending = []
    for row in rows:
        if not _needs_confirmation(row):
            continue
        evidence = session.get(SourceEvidenceRow, row.source_evidence_id)
        pending.append({
            "rule_id": str(row.id),
            "asset_type": row.asset_type,
            "field": row.field,
            "operator": row.operator,
            "value": row.expected_value_json,
            "confidence": row.confidence,
            "source_url": evidence.url if evidence else None,
            "source_excerpt": evidence.quoted_excerpt if evidence else None,
            "retrieved_at": evidence.retrieved_at.isoformat() if evidence else None,
            "question": (
                f"Does the source state that {row.asset_type} {row.field} "
                f"must be {row.operator} {row.expected_value_json}?"
            ),
        })
    return pending
