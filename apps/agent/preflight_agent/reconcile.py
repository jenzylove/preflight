"""Reconciling multiple sources for one destination.

A destination usually publishes its requirements across several pages, and
those pages do not always agree. When two official sources state incompatible
values for the same property, the honest answer is not to pick one — it is to
mark the requirement ambiguous, show the user both sources, and refuse to
certify anything that depends on it.
"""

from __future__ import annotations

from dataclasses import dataclass

from preflight_contracts.compare import describe_rule, mutually_exclusive
from preflight_contracts.rules import Rule, RulePack, Severity, SourceEvidence


@dataclass(frozen=True)
class Ambiguity:
    asset_type: str
    field_name: str
    rule_ids: tuple[str, ...]
    statements: tuple[str, ...]
    urls: tuple[str, ...]

    def explain(self) -> str:
        pairs = "\n".join(
            f"    {url} states {statement}"
            for url, statement in zip(self.urls, self.statements, strict=False)
        )
        return (
            f"{self.asset_type}.{self.field_name} is stated inconsistently by "
            f"official sources:\n{pairs}"
        )


def find_ambiguities(
    rules: list[Rule], evidence: dict[str, SourceEvidence]
) -> list[Ambiguity]:
    """Detect same-destination contradictions between assertable rules."""
    assertable = [r for r in rules if r.severity is not Severity.CONTEXT]
    by_field: dict[tuple[str, str], list[Rule]] = {}
    for rule in assertable:
        by_field.setdefault((rule.asset_type.value, rule.field_name), []).append(rule)

    ambiguities: list[Ambiguity] = []
    for (asset_type, field_name), group in by_field.items():
        if len(group) < 2:
            continue

        conflicting: list[Rule] = []
        for i in range(len(group)):
            for j in range(i + 1, len(group)):
                if mutually_exclusive(group[i], group[j]):
                    for rule in (group[i], group[j]):
                        if rule not in conflicting:
                            conflicting.append(rule)

        if not conflicting:
            continue

        ambiguities.append(
            Ambiguity(
                asset_type=asset_type,
                field_name=field_name,
                rule_ids=tuple(r.rule_id for r in conflicting),
                statements=tuple(describe_rule(r) for r in conflicting),
                urls=tuple(
                    evidence[r.source_evidence_id].url
                    for r in conflicting
                    if r.source_evidence_id in evidence
                ),
            )
        )
    return ambiguities


def deduplicate(rules: list[Rule]) -> list[Rule]:
    """Collapse rules that say the same thing.

    Several official pages repeating one requirement is corroboration, not
    three requirements. The strongest severity and highest confidence survive,
    and the first source keeps attribution.
    """
    order = {Severity.REQUIRED: 0, Severity.RECOMMENDED: 1, Severity.CONTEXT: 2}
    confidence_order = {"high": 0, "medium": 1, "low": 2}

    best: dict[str, Rule] = {}
    for rule in rules:
        key = rule.digest()
        current = best.get(key)
        if current is None:
            best[key] = rule
            continue
        stronger = order[rule.severity] < order[current.severity]
        surer = (
            order[rule.severity] == order[current.severity]
            and confidence_order[rule.confidence.value]
            < confidence_order[current.confidence.value]
        )
        if stronger or surer:
            best[key] = rule
    return list(best.values())


def build_pack(
    destination_id: str,
    version: int,
    rules: list[Rule],
    evidence: dict[str, SourceEvidence],
) -> RulePack:
    kept = deduplicate(rules)
    used = {r.source_evidence_id for r in kept}
    return RulePack(
        destination_id=destination_id,
        version=version,
        rules=kept,
        evidence={k: v for k, v in evidence.items() if k in used},
    )
