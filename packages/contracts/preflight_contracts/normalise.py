"""Recovering alternatives from a flattened rule pack.

Published specifications describe delivery *options*. Artdocfest lists SD, HD,
FullHD, 2K and 4K tiers, each with its own resolution and bitrate window, and
separately accepts DCP, ProRes and MP4. Extraction reads those tables row by
row and emits each cell as its own mandatory rule, which flattens a menu into a
contradiction: width must be 1280 and 2048 and 4096, simultaneously.

No file can satisfy that, so every delivery blocks on a disagreement the
destination never expressed.

This module puts the menu back together. Mandatory rules on the same property,
from the same destination, that cannot all hold at once are not a contradiction
between sources — they are alternatives, and satisfying any one satisfies the
requirement.

What it deliberately does not do is collapse rules that *can* all hold. Those
are genuine corroboration or genuine constraint, and merging them would discard
information. It also never collapses across destinations: the Berlinale
requiring burned-in subtitles while Artdocfest forbids them is a real conflict
and must survive.
"""

from __future__ import annotations

from collections import defaultdict

from .compare import mutually_exclusive
from .rules import AssetType, Operator, Rule, RulePack, Severity

_INF = float("inf")


def _is_numeric_window(rule: Rule) -> bool:
    """Anything that describes a span of acceptable numbers.

    Open-ended bounds count: "at most 20 Mbps" and "20 to 30 Mbps" are both
    windows, and a destination listing both alongside "90 to 120 Mbps" is
    listing tiers. Excluding gte and lte here left those groups uncollapsed and
    unsatisfiable.
    """
    return rule.operator in (
        Operator.BETWEEN, Operator.ANY_OF_RANGES, Operator.GTE, Operator.LTE,
    )


def _windows(rule: Rule) -> list[list[float]]:
    if rule.operator is Operator.BETWEEN:
        return [[float(rule.value[0]), float(rule.value[1])]]
    if rule.operator is Operator.GTE:
        return [[float(rule.value), _INF]]
    if rule.operator is Operator.LTE:
        return [[-_INF, float(rule.value)]]
    return [[float(lo), float(hi)] for lo, hi in rule.value]


def _merge_windows(windows: list[list[float]]) -> list[list[float]]:
    """Union of ranges, with touching or overlapping spans joined."""
    ordered = sorted(windows, key=lambda w: (w[0], w[1]))
    merged: list[list[float]] = []
    for low, high in ordered:
        if merged and low <= merged[-1][1]:
            merged[-1][1] = max(merged[-1][1], high)
        else:
            merged.append([low, high])
    return merged


def _is_set(rule: Rule) -> bool:
    return rule.operator in (Operator.EQ, Operator.IN)


def _members(rule: Rule) -> list:
    return list(rule.value) if rule.operator is Operator.IN else [rule.value]


def collapse_alternatives(rules: list[Rule]) -> tuple[list[Rule], list[dict]]:
    """Fold mutually exclusive same-field requirements into one disjunction.

    Returns the rewritten rules and a record of what was collapsed, so the
    change is auditable rather than silent — a user who wonders why five
    resolution rules became one can see which five.
    """
    grouped: dict[tuple[AssetType, str, str], list[Rule]] = defaultdict(list)
    passthrough: list[Rule] = []

    for rule in rules:
        if rule.severity is Severity.REQUIRED:
            grouped[(rule.asset_type, rule.field_name, rule.condition_key())].append(rule)
        else:
            passthrough.append(rule)

    collapsed: list[Rule] = []
    notes: list[dict] = []

    for (asset_type, field_name, _condition), group in grouped.items():
        if len(group) < 2:
            collapsed.extend(group)
            continue

        exclusive = any(
            mutually_exclusive(a, b)
            for i, a in enumerate(group)
            for b in group[i + 1:]
        )
        if not exclusive:
            # They can all hold. That is corroboration or genuine constraint,
            # and merging would throw information away.
            collapsed.extend(group)
            continue

        merged = _combine(group)
        if merged is None:
            # Alternatives exist but cannot be expressed as one rule. Keeping
            # them separate and letting the ambiguity surface is more honest
            # than inventing a shape for them.
            collapsed.extend(group)
            continue

        collapsed.append(merged)
        notes.append({
            "assetType": asset_type.value,
            "field": field_name,
            "collapsedFrom": len(group),
            "alternatives": [r.digest() for r in group],
            "reason": "the destination publishes these as alternative delivery options",
        })

    return collapsed + passthrough, notes


def _combine(group: list[Rule]) -> Rule | None:
    """Build one rule admitting everything the alternatives admit."""
    first = group[0]

    if all(_is_numeric_window(r) for r in group):
        windows = _merge_windows([w for r in group for w in _windows(r)])
        if len(windows) == 1:
            low, high = windows[0]
            # The union turned out contiguous, so say it in the plainest form
            # the bounds allow.
            if low == -_INF:
                return _rewrite(first, Operator.LTE, high, group)
            if high == _INF:
                return _rewrite(first, Operator.GTE, low, group)
            return _rewrite(first, Operator.BETWEEN, [low, high], group)
        return _rewrite(first, Operator.ANY_OF_RANGES, windows, group)

    if all(_is_set(r) for r in group):
        seen: list = []
        for rule in group:
            for member in _members(rule):
                if member not in seen:
                    seen.append(member)
        return _rewrite(first, Operator.IN, seen, group)

    return None


def _rewrite(template: Rule, operator: Operator, value, group: list[Rule]) -> Rule:
    sources = sorted({r.source_evidence_id for r in group})
    return Rule(
        rule_id=template.rule_id,
        asset_type=template.asset_type,
        field_name=template.field_name,
        operator=operator,
        value=value,
        severity=Severity.REQUIRED,
        # Attribution stays with the first contributing source; the note names
        # how many others agreed that this is a menu rather than a mandate.
        source_evidence_id=template.source_evidence_id,
        confidence=min((r.confidence for r in group), key=lambda c: c.value),
        note=(
            f"{template.note + ' ' if template.note else ''}"
            f"Published as {len(group)} alternative delivery options"
            f"{' across ' + str(len(sources)) + ' sources' if len(sources) > 1 else ''}."
        ).strip(),
        applies_when=dict(template.applies_when),
    )


def normalise_pack(pack: RulePack) -> tuple[RulePack, list[dict]]:
    """Return the pack with alternatives folded, plus what changed."""
    rules, notes = collapse_alternatives(pack.rules)
    used = {r.source_evidence_id for r in rules}
    return (
        RulePack(
            destination_id=pack.destination_id,
            version=pack.version,
            rules=rules,
            evidence={k: v for k, v in pack.evidence.items() if k in used},
            schema_version=pack.schema_version,
        ),
        notes,
    )


def deduplicate_conflicts(conflicts: list[dict]) -> list[dict]:
    """Collapse repeated reports of the same underlying disagreement.

    Two destinations disagreeing about subtitle format is one finding, however
    many extracted rule pairs express it. Reporting it eleven times buries the
    one thing the user needs to decide.
    """
    seen: dict[tuple, dict] = {}

    for conflict in conflicts:
        key = (
            conflict.get("assetType"),
            conflict.get("field"),
            tuple(sorted(conflict.get("destinations", []))),
            conflict.get("strength"),
        )
        existing = seen.get(key)
        if existing is None:
            merged = dict(conflict)
            merged["occurrences"] = 1
            seen[key] = merged
            continue

        existing["occurrences"] += 1
        # Keep every distinct wording; the user may recognise one and not another.
        for i, statement in enumerate(conflict.get("requirements", [])):
            phrasings = existing.setdefault("alsoStated", [[], []])
            if i < len(phrasings) and statement not in phrasings[i]:
                if statement != existing["requirements"][i]:
                    phrasings[i].append(statement)

    ordered = sorted(
        seen.values(),
        key=lambda c: (c.get("strength") != "hard", -c.get("occurrences", 1), c.get("field", "")),
    )
    return ordered
