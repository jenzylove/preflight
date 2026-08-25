"""The real job: fetch, repair, package, validate.

The order here is the safety model made executable.

  1. Re-check the approval. The plan is loaded fresh and its digest compared
     against the stored approval, so an approval cannot be replayed against a
     plan the user has not seen.
  2. Fetch the originals from private storage into a temporary workspace.
  3. Execute only green steps, writing new files. Originals are never opened
     for writing.
  4. Assemble one package per destination, because destinations that conflict
     cannot share an output.
  5. Validate each package by re-measuring what was actually written.
  6. Persist. A package reaches VERIFIED only if validation says so, and the
     database refuses to store it otherwise.

The worker never decides that its own output is good.
"""

from __future__ import annotations

import logging
import uuid
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

from preflight_contracts import repairs
from preflight_contracts.plan import OPERATION_CATALOGUE, Safety
from preflight_contracts.rules import RulePack
from preflight_contracts.state import JobState, PackageState

from . import storage
from .executor import assemble_package, run_job, temporary_workspace
from .validate import VALIDATOR_VERSION, validate_package

logger = logging.getLogger("preflight.worker.jobs")


class JobRefused(RuntimeError):
    """The job must not run. Retrying will not change that."""


def _now() -> datetime:
    return datetime.now(UTC).replace(tzinfo=None)


def process_job(job_id: uuid.UUID, session) -> dict[str, Any]:
    """Run one approved repair plan end to end."""
    from preflight_contracts.models import (
        Approval,
        Asset,
        Job,
        Project,
        RepairPlan,
        RepairStep,
    )
    from preflight_contracts.rulepacks import load_project_rule_packs
    from sqlalchemy import select

    job = session.get(Job, job_id)
    if job is None:
        raise JobRefused("no such job")

    if job.state in (JobState.SUCCEEDED.value, JobState.CANCELLED.value):
        # Cloud Tasks delivers at least once. A finished job is not redone.
        return {"state": job.state, "note": "already finished"}

    project = session.get(Project, job.project_id)
    if project is None:
        raise JobRefused("job has no project")

    plan_row = session.scalar(
        select(RepairPlan)
        .where(RepairPlan.project_id == project.id)
        .order_by(RepairPlan.created_at.desc())
    )
    if plan_row is None:
        raise JobRefused("no repair plan for this project")

    approval = session.scalar(
        select(Approval).where(
            Approval.project_id == project.id,
            Approval.repair_plan_digest == plan_row.digest,
        )
    )
    if approval is None:
        raise JobRefused(
            "the plan changed after approval; execution needs a fresh approval"
        )

    job.state = JobState.RUNNING.value
    job.attempt_count += 1
    job.started_at = job.started_at or _now()
    session.flush()

    steps = session.scalars(
        select(RepairStep).where(RepairStep.repair_plan_id == plan_row.id)
    ).all()
    approved_ids = {str(x) for x in (approval.approved_step_ids_json or [])}
    runnable = [
        s for s in steps
        if s.safety_level == Safety.GREEN.value
        and (not approved_ids or str(s.id) in approved_ids)
    ]

    assets = session.scalars(
        select(Asset).where(
            Asset.project_id == project.id,
            Asset.deleted_at.is_(None),
            Asset.sha256.is_not(None),
        )
    ).all()
    if not assets:
        raise JobRefused("no measured assets to work from")

    packs, _evidence, ambiguous = load_project_rule_packs(project.id, session)
    if not packs:
        raise JobRefused("no confirmed requirements to validate against")

    with temporary_workspace() as tmp:
        work = Path(tmp)
        inputs: dict[str, Path] = {}
        original_hashes: dict[str, str] = {}

        for asset in assets:
            local = work / "in" / f"{asset.role}{Path(asset.storage_key).suffix}"
            storage.download(asset.storage_key, local)
            inputs[asset.role] = local
            original_hashes[asset.role] = asset.sha256 or ""

        step_dicts = [
            {
                "step_id": str(s.id),
                "operation": s.operation,
                "input_role": OPERATION_CATALOGUE[s.operation]["input_role"],
                "output_role": s.output_role,
                "parameters": s.parameters_json or {},
                "depends_on": tuple(s.dependency_ids_json or ()),
            }
            for s in runnable
            if s.operation in OPERATION_CATALOGUE
        ]

        result = run_job(
            step_dicts,
            inputs=dict(inputs),
            work_dir=work / "out",
            plan_digest=plan_row.digest,
            approved_digest=approval.repair_plan_digest,
        )

        for outcome, step in zip(result.outcomes, runnable, strict=False):
            step.state = outcome.status
        session.flush()

        # Upload derived assets so they outlive the workspace.
        derived_records: list[dict[str, Any]] = []
        for outcome in result.outcomes:
            if outcome.status != "SUCCEEDED" or outcome.output_path is None:
                continue
            key = storage.derived_key(
                str(project.id), plan_row.digest, outcome.output_path.name
            )
            storage.upload(outcome.output_path, key)
            derived_records.append({
                "operation": outcome.operation,
                "parameters": outcome.parameters,
                "outputSha256": outcome.output_sha256,
                "inputSha256": outcome.input_sha256,
                "picturePreserved": outcome.picture_preserved,
                "storageKey": key,
            })

        by_role: dict[str, Path] = {}
        for outcome in result.outcomes:
            if outcome.status == "SUCCEEDED" and outcome.output_path is not None:
                step = next((s for s in runnable if str(s.id) == outcome.step_id), None)
                if step is not None:
                    by_role[OPERATION_CATALOGUE[step.operation]["input_role"]] = (
                        outcome.output_path
                    )

        packages_out: list[dict[str, Any]] = []
        for pack in packs:
            record = _build_and_validate(
                pack=pack,
                project=project,
                plan_row=plan_row,
                inputs=inputs,
                repaired=by_role,
                work=work,
                ambiguous=frozenset(ambiguous),
                session=session,
                derived_records=derived_records,
            )
            packages_out.append(record)

    any_failed = any(o.status != "SUCCEEDED" for o in result.outcomes)
    job.state = JobState.FAILED.value if any_failed else JobState.SUCCEEDED.value
    job.completed_at = _now()
    if any_failed:
        refused = [o for o in result.outcomes if o.status == "REFUSED"]
        job.error_code = "PLAN_CHANGED" if refused else "REPAIR_FAILED"
    session.flush()

    return {
        "state": job.state,
        "steps": [o.to_dict() for o in result.outcomes],
        "packages": packages_out,
        "validator": VALIDATOR_VERSION,
    }


def _build_and_validate(
    *,
    pack: RulePack,
    project,
    plan_row,
    inputs: dict[str, Path],
    repaired: dict[str, Path],
    work: Path,
    ambiguous: frozenset[str],
    session,
    derived_records: list[dict[str, Any]],
) -> dict[str, Any]:
    """Assemble one destination's package and decide whether it may verify."""
    from preflight_contracts.models import Destination, Package
    from sqlalchemy import select

    destination = session.scalar(
        select(Destination).where(Destination.slug == pack.destination_id)
    )
    if destination is None:
        return {"destination": pack.destination_id, "state": "SKIPPED",
                "reason": "unknown destination"}

    package_dir = work / "pkg" / pack.destination_id
    assemble_package(
        outputs=repaired,
        originals=inputs,
        destination_id=pack.destination_id,
        rule_pack_digest=pack.digest(),
        package_dir=package_dir,
    )

    # Independent: measures what was written, shares no state with the executor.
    report = validate_package(
        package_dir, pack, ambiguous_rule_ids=ambiguous, rule_pack_version_pinned=True
    )

    archive = storage.write_zip(package_dir, work / "zip" / f"{pack.destination_id}.zip")
    key = storage.package_key(str(project.id), plan_row.digest, pack.destination_id)
    storage.upload(archive, key, content_type="application/zip")
    archive_sha = repairs.sha256_file(archive)

    row = session.scalar(
        select(Package).where(
            Package.project_id == project.id,
            Package.destination_id == destination.id,
        )
    )
    pack_row_id = _rule_pack_row_id(destination.id, session)
    if row is None:
        row = Package(
            project_id=project.id,
            destination_id=destination.id,
            rule_pack_id=pack_row_id,
            state=PackageState.PLANNED.value,
        )
        session.add(row)
        session.flush()

    manifest = report.to_dict()
    manifest["destinationId"] = pack.destination_id
    manifest["transformations"] = derived_records
    manifest["files"] = [
        {"path": p.relative_to(package_dir).as_posix(),
         "sha256": repairs.sha256_file(p)}
        for p in sorted(package_dir.rglob("*")) if p.is_file()
    ]
    manifest["limitations"] = report.refusals

    row.storage_key = key
    row.sha256 = archive_sha
    row.manifest_json = manifest
    row.validated_against_output = True
    # The validator decides. The worker only records what it was told.
    row.state = (
        PackageState.VERIFIED.value if report.verified else PackageState.FAILED.value
    )
    session.flush()

    return {
        "destination": pack.destination_id,
        "state": row.state,
        "verified": report.verified,
        "packageSha256": archive_sha,
        "refusals": report.refusals,
    }


def _rule_pack_row_id(destination_id, session):
    from preflight_contracts.models import RulePackRow
    from sqlalchemy import select

    row = session.scalar(
        select(RulePackRow)
        .where(RulePackRow.destination_id == destination_id,
               RulePackRow.status == "CONFIRMED")
        .order_by(RulePackRow.version.desc())
    )
    return row.id if row else None
