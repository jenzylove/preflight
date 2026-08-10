"""Independent revalidation.

This module exists because a worker exiting zero proves only that a process
ended. It does not prove the poster is the right size, that the loudness landed
in the published window, or that the file it wrote is the file being shipped.

So validation re-measures the produced package from disk, with the same
deterministic tools used on the originals, and evaluates the destination's
rules against those fresh measurements. It deliberately shares no state with
the executor: it is handed a directory and told which rules to satisfy.

``validated_against_output`` is set here and nowhere else. The database refuses
to store a VERIFIED package without it.
"""

from __future__ import annotations

import logging
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

from preflight_contracts import inspect_media, repairs
from preflight_contracts.compare import Assertion, Result, evaluate_pack, is_ready
from preflight_contracts.rules import AssetType, RulePack, Severity
from preflight_contracts.state import may_verify

logger = logging.getLogger("preflight.validate")

VALIDATOR_VERSION = "1.0.0"

_SUFFIX_ROLE = {
    ".mp4": "master", ".mov": "master",
    ".srt": "subtitle", ".vtt": "subtitle",
    ".jpg": "poster", ".jpeg": "poster", ".png": "poster",
}


@dataclass
class ValidationReport:
    destination_id: str
    assertions: list[Assertion] = field(default_factory=list)
    measured: dict[str, dict] = field(default_factory=dict)
    manifest_verified: bool = False
    package_sha256: str | None = None
    verified: bool = False
    refusals: list[str] = field(default_factory=list)
    validator_version: str = VALIDATOR_VERSION

    def to_dict(self) -> dict[str, Any]:
        return {
            "destinationId": self.destination_id,
            "validatorVersion": self.validator_version,
            "verified": self.verified,
            "refusals": self.refusals,
            "manifestVerified": self.manifest_verified,
            "packageSha256": self.package_sha256,
            "measured": self.measured,
            "assertions": [
                {
                    "ruleId": a.rule_id,
                    "field": f"{a.asset_type.value}.{a.field_name}",
                    "published": a.expected,
                    "measured": a.measured,
                    "result": a.result.value,
                    "severity": a.severity.value,
                }
                for a in self.assertions
            ],
        }


def measure_package(package_dir: Path) -> dict[AssetType, dict]:
    """Measure every asset in a built package, from disk.

    Roles are inferred from the file extension rather than trusted from a
    manifest, so a manifest that misdescribes its own contents cannot steer
    validation away from the real files.
    """
    measured: dict[AssetType, dict] = {}

    for path in sorted(package_dir.rglob("*")):
        if not path.is_file() or path.name == "manifest.json":
            continue
        role = _SUFFIX_ROLE.get(path.suffix.lower())
        if role is None:
            continue

        try:
            if role == "master":
                video = inspect_media.inspect_video(path)
                audio = inspect_media.inspect_audio(path)
                measured[AssetType.VIDEO] = video.properties
                measured[AssetType.AUDIO] = {
                    k: v for k, v in audio.properties.items() if not k.startswith("_")
                }
            elif role == "subtitle":
                measured[AssetType.SUBTITLE] = inspect_media.inspect_subtitle(path).properties
            elif role == "poster":
                measured[AssetType.POSTER] = inspect_media.inspect_poster(path).properties
        except inspect_media.InspectionError as exc:
            # An output that cannot be measured cannot be verified. This is the
            # AC-7 case: the worker succeeded, the file is unusable.
            logger.warning("output %s could not be measured: %s", path.name, exc)

    return measured


def verify_manifest(package_dir: Path) -> tuple[bool, list[str]]:
    """Recompute every hash in the manifest against the files on disk."""
    import json

    manifest_path = package_dir / "manifest.json"
    if not manifest_path.exists():
        return False, ["package has no manifest"]

    try:
        manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as exc:
        return False, [f"manifest could not be read: {exc}"]

    problems: list[str] = []
    listed = set()
    for entry in manifest.get("files", []):
        relative = entry.get("path", "")
        listed.add(relative)
        target = package_dir / relative
        if not target.exists():
            problems.append(f"{relative} is listed in the manifest but missing")
            continue
        if repairs.sha256_file(target) != entry.get("sha256"):
            problems.append(f"{relative} does not match its recorded hash")

    on_disk = {
        p.relative_to(package_dir).as_posix()
        for p in package_dir.rglob("*")
        if p.is_file() and p.name != "manifest.json"
    }
    for extra in sorted(on_disk - listed):
        problems.append(f"{extra} is present but not recorded in the manifest")

    return (not problems), problems


def validate_package(
    package_dir: Path,
    pack: RulePack,
    *,
    ambiguous_rule_ids: frozenset[str] = frozenset(),
    rule_pack_version_pinned: bool = True,
) -> ValidationReport:
    """Decide whether a built package may be called verified.

    Every input to the decision is measured here. Nothing is inherited from the
    preflight run that planned the work.
    """
    report = ValidationReport(destination_id=pack.destination_id)

    measured = measure_package(package_dir)
    report.measured = {k.value: v for k, v in measured.items()}

    report.assertions = [
        a for a in evaluate_pack(pack, measured, ambiguous_rule_ids)
        if a.result is not Result.NOT_APPLICABLE
    ]

    manifest_ok, manifest_problems = verify_manifest(package_dir)
    report.manifest_verified = manifest_ok
    report.refusals.extend(manifest_problems)

    report.package_sha256 = _package_hash(package_dir)

    required = [a for a in report.assertions if a.severity is Severity.REQUIRED]
    allowed, reasons = may_verify(
        required_assertions_all_pass=is_ready(report.assertions),
        any_required_ambiguous=any(a.result is Result.AMBIGUOUS for a in required),
        any_required_unsupported=any(a.result is Result.UNSUPPORTED for a in required),
        package_hash_present=bool(report.package_sha256),
        manifest_verified=manifest_ok,
        # True precisely because every measurement above came from the built
        # package. This is the only place in the system that may assert it.
        validated_against_output=True,
        rule_pack_version_pinned=rule_pack_version_pinned,
    )

    report.verified = allowed
    report.refusals.extend(reasons)

    if not allowed:
        failing = [
            f"{a.asset_type.value}.{a.field_name} ({a.result.value})"
            for a in required if a.result is not Result.PASS
        ]
        if failing:
            report.refusals.append("unsatisfied: " + ", ".join(failing))

    return report


def _package_hash(package_dir: Path) -> str | None:
    """One hash over the whole package, stable regardless of file order."""
    import hashlib

    files = sorted(
        (p for p in package_dir.rglob("*") if p.is_file()),
        key=lambda p: p.relative_to(package_dir).as_posix(),
    )
    if not files:
        return None

    digest = hashlib.sha256()
    for path in files:
        digest.update(path.relative_to(package_dir).as_posix().encode())
        digest.update(repairs.sha256_file(path).encode())
    return digest.hexdigest()
