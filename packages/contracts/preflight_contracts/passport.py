"""The release passport.

A passport is the answer to "what exactly did you send them, and how do you
know it was right". It records the original hashes, every transformation, the
rule versions those transformations were made against, the sources those rules
came from, the validator's results, and — the part most systems omit — what
Preflight could not settle.

Two rules govern it:

**A passport is immutable once issued.** If a destination changes its
requirements next week, an exported passport still says what was true when the
delivery was made. Rewriting history to match a newer spec would destroy the
only thing a passport is for.

**Limitations are never omitted.** A verified package that hides what it could
not check is more dangerous than an unverified one, because the reader stops
looking.
"""

from __future__ import annotations

import hashlib
import json
from dataclasses import dataclass, field
from datetime import UTC, datetime
from typing import Any

PASSPORT_SCHEMA_VERSION = "1.0.0"

#: Stated on every passport, in the passport itself, not only in the UI.
#: Preflight measures against published requirements. It has no visibility into
#: whether a festival programmer or a platform's QC team will accept a film.
STANDING_LIMITATION = (
    "Preflight verifies this package against the destination requirements "
    "published at the retrieval dates recorded below. It is not a guarantee "
    "that the destination will accept this delivery."
)


@dataclass
class AssetLineage:
    role: str
    original_filename: str
    original_sha256: str
    derived_sha256: str | None = None
    picture_sha: str | None = None
    picture_preserved: bool | None = None
    transformations: list[dict[str, Any]] = field(default_factory=list)

    @property
    def was_modified(self) -> bool:
        return bool(self.transformations)

    def to_dict(self) -> dict[str, Any]:
        return {
            "role": self.role,
            "originalFilename": self.original_filename,
            "originalSha256": self.original_sha256,
            "derivedSha256": self.derived_sha256,
            "pictureHash": self.picture_sha,
            "picturePreserved": self.picture_preserved,
            "wasModified": self.was_modified,
            "transformations": self.transformations,
        }


@dataclass
class DestinationRecord:
    destination_id: str
    rule_pack_version: int
    rule_pack_digest: str
    sources: list[dict[str, str]]
    package_sha256: str | None
    manifest_digest: str | None
    verified: bool
    assertions_passed: int
    assertions_total: int
    refusals: list[str] = field(default_factory=list)

    def to_dict(self) -> dict[str, Any]:
        return {
            "destinationId": self.destination_id,
            "rulePackVersion": self.rule_pack_version,
            "rulePackDigest": self.rule_pack_digest,
            "sources": self.sources,
            "packageSha256": self.package_sha256,
            "manifestDigest": self.manifest_digest,
            "verified": self.verified,
            "requirementsSatisfied": f"{self.assertions_passed}/{self.assertions_total}",
            "notVerifiedBecause": self.refusals,
        }


@dataclass
class Passport:
    project_id: str
    project_title: str
    version: int
    issued_at: str
    assets: list[AssetLineage] = field(default_factory=list)
    destinations: list[DestinationRecord] = field(default_factory=list)
    repair_plan_digest: str = ""
    approved_at: str | None = None
    approved_steps: list[str] = field(default_factory=list)
    validator_version: str = ""
    tool_versions: dict[str, str] = field(default_factory=dict)
    limitations: list[str] = field(default_factory=list)
    schema_version: str = PASSPORT_SCHEMA_VERSION

    def to_dict(self) -> dict[str, Any]:
        return {
            "schemaVersion": self.schema_version,
            "projectId": self.project_id,
            "projectTitle": self.project_title,
            "version": self.version,
            "issuedAt": self.issued_at,
            "assets": [a.to_dict() for a in self.assets],
            "destinations": [d.to_dict() for d in self.destinations],
            "approval": {
                "repairPlanDigest": self.repair_plan_digest,
                "approvedAt": self.approved_at,
                "approvedSteps": self.approved_steps,
            },
            "verification": {
                "validatorVersion": self.validator_version,
                "toolVersions": self.tool_versions,
            },
            "limitations": self.limitations,
            "digest": self.digest(),
        }

    def digest(self) -> str:
        """Identity of everything the passport asserts.

        Excludes issued_at so that re-serialising the same facts yields the
        same digest, and excludes the digest itself.
        """
        payload = json.dumps(
            {
                "projectId": self.project_id,
                "version": self.version,
                "assets": [a.to_dict() for a in self.assets],
                "destinations": [d.to_dict() for d in self.destinations],
                "approval": self.repair_plan_digest,
                "limitations": sorted(self.limitations),
            },
            sort_keys=True,
            separators=(",", ":"),
            default=str,
        )
        return hashlib.sha256(payload.encode()).hexdigest()[:32]

    def to_json(self) -> str:
        return json.dumps(self.to_dict(), indent=2, default=str)

    def to_report(self) -> str:
        """Human-readable receipt.

        Written for a producer sending it to a distributor, so it leads with
        what was delivered and ends with what is unresolved — not the other way
        round, which is how limitations get skipped.
        """
        lines = [
            f"RELEASE PASSPORT — {self.project_title}",
            f"Issued {self.issued_at}    Passport {self.digest()}",
            "=" * 72,
            "",
            "ORIGINAL ASSETS",
        ]
        for asset in self.assets:
            lines.append(f"  {asset.role:12} {asset.original_filename}")
            lines.append(f"  {'':12} sha256 {asset.original_sha256}")
            if asset.picture_preserved is True:
                lines.append(
                    f"  {'':12} picture unchanged through processing "
                    f"({asset.picture_sha})"
                )
            if not asset.was_modified:
                lines.append(f"  {'':12} not modified")
            for transformation in asset.transformations:
                lines.append(
                    f"  {'':12} -> {transformation.get('operation')} "
                    f"{_summarise(transformation.get('parameters', {}))}"
                )
            lines.append("")

        lines.append("DESTINATIONS")
        for record in self.destinations:
            status = "meets published requirements" if record.verified else "NOT VERIFIED"
            lines.append(f"  {record.destination_id}: {status}")
            lines.append(
                f"    requirements satisfied {record.assertions_passed}"
                f"/{record.assertions_total}"
                f"   rule pack v{record.rule_pack_version} ({record.rule_pack_digest})"
            )
            if record.package_sha256:
                lines.append(f"    package sha256 {record.package_sha256}")
            for source in record.sources:
                lines.append(
                    f"    source {source.get('url')} retrieved {source.get('retrievedAt')}"
                )
            for refusal in record.refusals:
                lines.append(f"    not verified because: {refusal}")
            lines.append("")

        if self.repair_plan_digest:
            lines.append("APPROVAL")
            lines.append(f"  plan {self.repair_plan_digest}")
            lines.append(f"  approved {self.approved_at}")
            lines.append("")

        lines.append("LIMITATIONS")
        for limitation in self.limitations:
            lines.append(f"  - {limitation}")

        return "\n".join(lines) + "\n"


def _summarise(parameters: dict[str, Any]) -> str:
    if not parameters:
        return ""
    return "(" + ", ".join(f"{k}={v}" for k, v in sorted(parameters.items())) + ")"


def build_passport(
    *,
    project_id: str,
    project_title: str,
    version: int,
    assets: list[AssetLineage],
    destinations: list[DestinationRecord],
    repair_plan_digest: str = "",
    approved_at: str | None = None,
    approved_steps: list[str] | None = None,
    validator_version: str = "",
    tool_versions: dict[str, str] | None = None,
    extra_limitations: list[str] | None = None,
) -> Passport:
    """Assemble a passport, with limitations gathered from the evidence.

    Limitations are derived here rather than passed in, so a caller cannot
    produce a clean-looking passport by forgetting to mention them.
    """
    limitations: list[str] = []

    unverified = [d for d in destinations if not d.verified]
    for record in unverified:
        reasons = "; ".join(record.refusals) or "requirements were not all satisfied"
        limitations.append(
            f"{record.destination_id}: this package was NOT verified — {reasons}"
        )

    unmodified = [a.role for a in assets if not a.was_modified]
    if unmodified:
        limitations.append(
            "Delivered unchanged from your original: " + ", ".join(sorted(unmodified))
        )

    limitations.extend(extra_limitations or [])
    limitations.append(STANDING_LIMITATION)

    return Passport(
        project_id=project_id,
        project_title=project_title,
        version=version,
        issued_at=datetime.now(UTC).isoformat(timespec="seconds"),
        assets=assets,
        destinations=destinations,
        repair_plan_digest=repair_plan_digest,
        approved_at=approved_at,
        approved_steps=approved_steps or [],
        validator_version=validator_version,
        tool_versions=tool_versions or {},
        limitations=limitations,
    )
