"""Packages and the release passport.

A package is what a destination actually receives. Where destinations conflict,
there is more than one, and the difference between them is the product working
rather than a defect.

The passport is assembled from what the database recorded, not from what the
UI would like to display. If a package was not verified, the passport says so
and names the reason.
"""

from __future__ import annotations

import uuid
from datetime import datetime
from typing import Any

from fastapi import APIRouter, Depends, HTTPException, status
from preflight_contracts.passport import (
    AssetLineage,
    DestinationRecord,
    build_passport,
)
from preflight_contracts.state import PackageState
from pydantic import BaseModel
from sqlalchemy import select
from sqlalchemy.orm import Session

from ..assets import storage
from ..auth.identity import owned_project
from ..core.db import get_session
from ..core.models import (
    Approval,
    Asset,
    AssetEvidence,
    Destination,
    Package,
    Passport,
    Project,
    RepairPlan,
    RuleDisposition,
    RulePackRow,
    RuleRow,
    SourceEvidenceRow,
)

router = APIRouter(prefix="/v1/projects/{project_id}", tags=["packages"])


class FileOut(BaseModel):
    path: str
    sha256: str


class TransformationOut(BaseModel):
    operation: str
    parameters: dict[str, Any]
    input_sha256: str | None = None
    output_sha256: str | None = None
    picture_preserved: bool | None = None


class PackageOut(BaseModel):
    id: uuid.UUID
    destination_id: str
    destination_name: str
    state: str
    verified: bool
    package_sha256: str | None
    rule_pack_version: int | None
    rule_pack_digest: str | None
    requirements_satisfied: str
    files: list[FileOut]
    transformations: list[TransformationOut]
    limitations: list[str]
    validator_version: str | None
    created_at: datetime


def _package_out(row: Package, session: Session) -> PackageOut:
    destination = session.get(Destination, row.destination_id)
    manifest: dict[str, Any] = row.manifest_json or {}
    assertions = manifest.get("assertions", [])
    satisfied = sum(1 for a in assertions if a.get("result") == "PASS")

    pack_row = session.get(RulePackRow, row.rule_pack_id) if row.rule_pack_id else None

    return PackageOut(
        id=row.id,
        destination_id=manifest.get("destinationId") or (
            destination.slug if destination else "unknown"
        ),
        destination_name=destination.name if destination else "Unknown destination",
        state=row.state,
        verified=row.state == PackageState.VERIFIED.value,
        package_sha256=row.sha256,
        rule_pack_version=pack_row.version if pack_row else None,
        rule_pack_digest=pack_row.digest if pack_row else None,
        requirements_satisfied=f"{satisfied}/{len(assertions)}" if assertions else "0/0",
        files=[
            FileOut(path=f.get("path", ""), sha256=f.get("sha256", ""))
            for f in manifest.get("files", [])
        ],
        transformations=[
            TransformationOut(
                operation=t.get("operation", ""),
                parameters=t.get("parameters", {}) or {},
                input_sha256=t.get("inputSha256"),
                output_sha256=t.get("outputSha256"),
                picture_preserved=t.get("picturePreserved"),
            )
            for t in manifest.get("transformations", [])
        ],
        limitations=manifest.get("limitations", []),
        validator_version=manifest.get("validatorVersion"),
        created_at=row.created_at,
    )


@router.get("/packages", response_model=list[PackageOut])
def list_packages(
    project: Project = Depends(owned_project),
    session: Session = Depends(get_session),
) -> list[PackageOut]:
    rows = session.scalars(
        select(Package)
        .where(Package.project_id == project.id)
        .order_by(Package.created_at)
    ).all()
    return [_package_out(r, session) for r in rows]


class DownloadOut(BaseModel):
    url: str
    expires_in_seconds: int
    sha256: str | None


@router.post("/packages/{package_id}/download-intent", response_model=DownloadOut)
def download_package(
    package_id: uuid.UUID,
    project: Project = Depends(owned_project),
    session: Session = Depends(get_session),
) -> DownloadOut:
    row = session.scalar(
        select(Package).where(
            Package.id == package_id, Package.project_id == project.id
        )
    )
    if row is None or not row.storage_key:
        raise HTTPException(status_code=404, detail="Not found")

    from ..core.config import get_settings

    try:
        url = storage.create_download_url(row.storage_key, f"{project.title}.zip")
    except storage.StorageError:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="This download is temporarily unavailable. Please try again.",
        ) from None

    return DownloadOut(
        url=url,
        expires_in_seconds=get_settings().signed_url_ttl_seconds,
        sha256=row.sha256,
    )


# ---------------------------------------------------------------------------
# Passport
# ---------------------------------------------------------------------------

class PassportOut(BaseModel):
    version: int
    digest: str
    issued_at: str
    passport: dict[str, Any]
    report: str


@router.get("/passport", response_model=PassportOut)
def get_passport(
    project: Project = Depends(owned_project),
    session: Session = Depends(get_session),
) -> PassportOut:
    """Assemble the passport from recorded evidence.

    Regenerated on read from the same rows every time, so it cannot drift from
    what the database holds. Once a version is stored it is never rewritten:
    a destination revising its requirements later does not change what was true
    at the moment of delivery.
    """
    packages = session.scalars(
        select(Package).where(Package.project_id == project.id)
    ).all()
    if not packages:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="No packages have been built for this project yet.",
        )

    assets = session.scalars(
        select(Asset).where(
            Asset.project_id == project.id, Asset.deleted_at.is_(None)
        )
    ).all()

    transformations_by_role: dict[str, list[dict]] = {}
    for package in packages:
        for t in (package.manifest_json or {}).get("transformations", []):
            role = _role_for_operation(t.get("operation", ""))
            transformations_by_role.setdefault(role, [])
            if t not in transformations_by_role[role]:
                transformations_by_role[role].append(t)

    lineage: list[AssetLineage] = []
    for asset in assets:
        evidence = session.scalar(
            select(AssetEvidence)
            .where(AssetEvidence.asset_id == asset.id)
            .order_by(AssetEvidence.created_at.desc())
        )
        measured = (evidence.measured_properties_json or {}) if evidence else {}
        picture = (measured.get("video") or {}).get("videoStreamMd5")
        applied = transformations_by_role.get(asset.role, [])
        lineage.append(AssetLineage(
            role=asset.role,
            original_filename=asset.original_filename,
            original_sha256=asset.sha256 or "",
            derived_sha256=applied[-1].get("outputSha256") if applied else None,
            picture_sha=picture,
            picture_preserved=(
                all(t.get("picturePreserved") is not False for t in applied)
                if applied else None
            ),
            transformations=[
                {"operation": t.get("operation"), "parameters": t.get("parameters", {})}
                for t in applied
            ],
        ))

    records: list[DestinationRecord] = []
    for package in packages:
        destination = session.get(Destination, package.destination_id)
        manifest = package.manifest_json or {}
        assertions = manifest.get("assertions", [])
        pack_row = (
            session.get(RulePackRow, package.rule_pack_id)
            if package.rule_pack_id else None
        )
        records.append(DestinationRecord(
            destination_id=destination.slug if destination else "unknown",
            rule_pack_version=pack_row.version if pack_row else 0,
            rule_pack_digest=pack_row.digest if pack_row else "",
            sources=_sources_for_pack(pack_row, session),
            package_sha256=package.sha256,
            manifest_digest=manifest.get("manifestDigest"),
            verified=package.state == PackageState.VERIFIED.value,
            assertions_passed=sum(1 for a in assertions if a.get("result") == "PASS"),
            assertions_total=len(assertions),
            refusals=manifest.get("limitations", []),
        ))

    plan_row = session.scalar(
        select(RepairPlan)
        .where(RepairPlan.project_id == project.id)
        .order_by(RepairPlan.created_at.desc())
    )
    approval = session.scalar(
        select(Approval)
        .where(Approval.project_id == project.id)
        .order_by(Approval.created_at.desc())
    )

    existing = session.scalar(
        select(Passport)
        .where(Passport.project_id == project.id)
        .order_by(Passport.version.desc())
    )
    version = (existing.version + 1) if existing else 1

    set_aside = session.scalars(
        select(RuleDisposition).where(
            RuleDisposition.project_id == project.id,
            RuleDisposition.action == "set_aside",
        )
    ).all()
    overrides = [
        f"A published requirement was set aside by the project owner and not "
        f"measured: {_describe_rule_row(session.get(RuleRow, d.rule_id))} "
        f"- {d.reason}"
        for d in set_aside
    ]

    passport = build_passport(
        project_id=str(project.id),
        project_title=project.title,
        version=version,
        assets=lineage,
        destinations=records,
        repair_plan_digest=plan_row.digest if plan_row else "",
        approved_at=approval.created_at.isoformat() if approval else None,
        approved_steps=[str(x) for x in (approval.approved_step_ids_json or [])]
        if approval else [],
        validator_version=(packages[0].manifest_json or {}).get("validatorVersion", ""),
        tool_versions=_tool_versions(assets, session),
        extra_limitations=overrides,
    )

    # Store the first issue; later reads reuse it rather than minting versions.
    if existing is None or existing.digest != passport.digest():
        session.add(Passport(
            project_id=project.id,
            version=version,
            digest=passport.digest(),
            passport_json=passport.to_dict(),
        ))
        session.flush()
    else:
        passport.version = existing.version

    return PassportOut(
        version=passport.version,
        digest=passport.digest(),
        issued_at=passport.issued_at,
        passport=passport.to_dict(),
        report=passport.to_report(),
    )


def _describe_rule_row(row: RuleRow | None) -> str:
    if row is None:
        return "an unknown requirement"
    return f"{row.asset_type}.{row.field} {row.operator} {row.expected_value_json}"


def _role_for_operation(operation: str) -> str:
    from preflight_contracts.plan import OPERATION_CATALOGUE

    spec = OPERATION_CATALOGUE.get(operation)
    return spec["input_role"] if spec else "master"


def _sources_for_pack(pack_row: RulePackRow | None, session: Session) -> list[dict]:
    if pack_row is None:
        return []
    rows = session.scalars(
        select(SourceEvidenceRow)
        .join(RuleRow, RuleRow.source_evidence_id == SourceEvidenceRow.id)
        .where(RuleRow.rule_pack_id == pack_row.id)
        .distinct()
    ).all()
    seen: dict[str, dict] = {}
    for row in rows:
        if row.private or not row.url or row.url in seen:
            continue
        seen[row.url] = {
            "url": row.url,
            "retrievedAt": row.retrieved_at.isoformat(),
            "trustTier": row.trust_tier,
        }
    return list(seen.values())


def _tool_versions(assets: list[Asset], session: Session) -> dict[str, str]:
    versions: dict[str, str] = {}
    for asset in assets:
        evidence = session.scalar(
            select(AssetEvidence)
            .where(AssetEvidence.asset_id == asset.id)
            .order_by(AssetEvidence.created_at.desc())
        )
        if evidence:
            versions[evidence.inspector] = evidence.inspector_version
    return versions
