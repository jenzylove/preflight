"""Evidence-bound corrections for known extraction scope mistakes."""

from __future__ import annotations

from .rules import AssetType, Operator, Rule, SourceEvidence


def is_dcp_only_isdcf_rule(rule: Rule, evidence: SourceEvidence) -> bool:
    """Identify ISDCF text scoped to Sundance's DCP section.

    Sundance's online screening file is a ProRes LT ``.mov``. Its official
    specification mentions ISDCF only in the separate in-person DCP section.
    A model that turns that convention name into ``package.fileNamePattern``
    has lost the source scope. Keep the rule available for review, but do not
    let it masquerade as an online filename requirement.
    """
    if (
        rule.asset_type is not AssetType.PACKAGE
        or rule.field_name != "fileNamePattern"
        or rule.operator is not Operator.EQ
        or str(rule.value).strip().lower() != "isdcf"
    ):
        return False

    excerpt = evidence.quoted_excerpt.lower()
    has_dcp_scope = "dcp" in excerpt or "digital cinema" in excerpt
    has_isdcf = "isdcf" in excerpt
    has_online_scope = any(
        marker in excerpt
        for marker in ("online screening", "online file", "online platform")
    )
    return has_dcp_scope and has_isdcf and not has_online_scope
