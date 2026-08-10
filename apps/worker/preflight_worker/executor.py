"""Repair execution.

Three properties hold here or the product's claims are false.

**Nothing runs that was not approved.** Every step is checked against the
approved plan digest and the closed operation catalogue before it executes. A
step whose operation is not green is refused even if it somehow reached the
worker.

**Retries do not duplicate.** Output keys are derived from the plan digest and
the step, so re-running a job overwrites the same object rather than creating a
second one. A crashed job is safe to restart.

**Success is not self-reported.** The worker produces outputs and stops. It
cannot mark anything verified — validation is a separate pass that measures
what was actually written, and the readiness predicate is evaluated from those
measurements.
"""

from __future__ import annotations

import logging
import shutil
import tempfile
from dataclasses import dataclass, field
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

from preflight_contracts import inspect_media, repairs
from preflight_contracts.plan import OPERATION_CATALOGUE, Safety

logger = logging.getLogger("preflight.worker")

WORKER_VERSION = "1.0.0"


class ExecutionRefused(RuntimeError):
    """Raised when a step must not run. Never caught and retried."""


@dataclass
class StepOutcome:
    step_id: str
    operation: str
    status: str                    # SUCCEEDED | REFUSED | FAILED
    output_path: Path | None = None
    output_sha256: str | None = None
    input_sha256: str | None = None
    picture_preserved: bool | None = None
    parameters: dict[str, Any] = field(default_factory=dict)
    error: str | None = None
    finished_at: str = ""

    def to_dict(self) -> dict[str, Any]:
        return {
            "stepId": self.step_id,
            "operation": self.operation,
            "status": self.status,
            "output": self.output_path.name if self.output_path else None,
            "outputSha256": self.output_sha256,
            "inputSha256": self.input_sha256,
            "picturePreserved": self.picture_preserved,
            "parameters": self.parameters,
            "error": self.error,
            "finishedAt": self.finished_at,
        }


@dataclass
class JobResult:
    plan_digest: str
    outcomes: list[StepOutcome] = field(default_factory=list)
    worker_version: str = WORKER_VERSION

    @property
    def succeeded(self) -> bool:
        return all(o.status == "SUCCEEDED" for o in self.outcomes)

    @property
    def outputs(self) -> dict[str, Path]:
        return {
            o.step_id: o.output_path
            for o in self.outcomes
            if o.status == "SUCCEEDED" and o.output_path is not None
        }


def _now() -> str:
    return datetime.now(UTC).isoformat(timespec="seconds")


def _guard_step(step: dict[str, Any], approved_digest: str, plan_digest: str) -> None:
    """Refuse anything not covered by the approval the user actually gave."""
    if not approved_digest or approved_digest != plan_digest:
        raise ExecutionRefused(
            "the plan has changed since it was approved; execution requires a "
            "fresh approval of the current plan"
        )

    operation = step.get("operation", "")
    spec = OPERATION_CATALOGUE.get(operation)
    if spec is None:
        raise ExecutionRefused(f"operation {operation!r} is not in the catalogue")
    if spec["safety"] is not Safety.GREEN:
        raise ExecutionRefused(
            f"operation {operation!r} is {spec['safety'].value} and is never "
            f"executed automatically"
        )


def output_name(plan_digest: str, step_id: str, operation: str, suffix: str) -> str:
    """Deterministic output name.

    Derived from the plan digest and step, so a retry writes to the same place.
    This is what makes the job idempotent at the storage layer rather than
    relying on the job never being run twice.
    """
    return f"{plan_digest[:16]}_{step_id}_{operation}{suffix}"


def execute_step(
    step: dict[str, Any],
    *,
    inputs: dict[str, Path],
    work_dir: Path,
    plan_digest: str,
    approved_digest: str,
) -> StepOutcome:
    operation = step.get("operation", "")
    step_id = step.get("step_id", "?")

    try:
        _guard_step(step, approved_digest, plan_digest)
    except ExecutionRefused as exc:
        logger.warning("refused step %s (%s): %s", step_id, operation, exc)
        return StepOutcome(step_id, operation, "REFUSED", error=str(exc), finished_at=_now())

    parameters = step.get("parameters", {}) or {}
    source = inputs.get(step.get("input_role", ""))
    if source is None or not source.exists():
        return StepOutcome(
            step_id, operation, "FAILED",
            error=f"input asset {step.get('input_role')!r} is not available",
            finished_at=_now(),
        )

    try:
        result = _dispatch(operation, source, work_dir, parameters, plan_digest, step_id)
    except (repairs.RepairError, inspect_media.InspectionError, OSError) as exc:
        logger.warning("step %s (%s) failed: %s", step_id, operation, exc)
        return StepOutcome(step_id, operation, "FAILED", error=str(exc)[:400],
                           finished_at=_now())

    return StepOutcome(
        step_id=step_id,
        operation=operation,
        status="SUCCEEDED",
        output_path=result.output_path,
        output_sha256=result.output_sha256,
        input_sha256=result.input_sha256,
        picture_preserved=result.picture_preserved,
        parameters=result.parameters,
        finished_at=_now(),
    )


def _dispatch(
    operation: str,
    source: Path,
    work_dir: Path,
    parameters: dict[str, Any],
    plan_digest: str,
    step_id: str,
) -> repairs.RepairResult:
    work_dir.mkdir(parents=True, exist_ok=True)

    if operation == "normalise_loudness":
        out = work_dir / output_name(plan_digest, step_id, operation, source.suffix)
        return repairs.normalise_loudness(
            source, out,
            target_lufs=float(parameters.get("targetLufs", -23.0)),
            true_peak_dbtp=float(parameters.get("truePeakDbtp", -3.0)),
        )

    if operation == "rewrite_container_metadata":
        out = work_dir / output_name(plan_digest, step_id, operation, source.suffix)
        return repairs.rewrite_container_metadata(
            source, out,
            display_aspect_ratio=parameters.get("displayAspectRatio", "16:9"),
            colour_primaries=parameters.get("colourPrimaries", "bt709"),
            colour_transfer=parameters.get("colourTransfer", "bt709"),
            colour_matrix=parameters.get("colourMatrix", "bt709"),
            fast_start=bool(parameters.get("fastStart", True)),
        )

    if operation == "convert_subtitles":
        target = str(parameters.get("targetFormat", "srt")).lower().lstrip(".")
        out = work_dir / output_name(plan_digest, step_id, operation, f".{target}")
        return repairs.convert_subtitles(source, out, target)

    if operation == "resize_poster":
        out = work_dir / output_name(plan_digest, step_id, operation, ".jpg")
        return repairs.resize_poster(
            source, out,
            width=int(parameters.get("width", 1920)),
            height=int(parameters.get("height", 1080)),
            mode=str(parameters.get("mode", "pad")),
        )

    raise ExecutionRefused(f"no handler for catalogued operation {operation!r}")


def run_job(
    steps: list[dict[str, Any]],
    *,
    inputs: dict[str, Path],
    work_dir: Path,
    plan_digest: str,
    approved_digest: str,
) -> JobResult:
    """Execute an approved plan in dependency order.

    A step whose dependency failed is not attempted: building on an output
    that does not exist would produce a package that looks complete and is not.
    """
    result = JobResult(plan_digest=plan_digest)
    produced: dict[str, Path] = dict(inputs)
    failed_steps: set[str] = set()

    for step in steps:
        dependencies = set(step.get("depends_on", ()) or ())
        if dependencies & failed_steps:
            result.outcomes.append(StepOutcome(
                step.get("step_id", "?"), step.get("operation", ""), "FAILED",
                error="a step this one depends on did not succeed",
                finished_at=_now(),
            ))
            failed_steps.add(step.get("step_id", "?"))
            continue

        outcome = execute_step(
            step,
            inputs=produced,
            work_dir=work_dir,
            plan_digest=plan_digest,
            approved_digest=approved_digest,
        )
        result.outcomes.append(outcome)

        if outcome.status == "SUCCEEDED" and outcome.output_path is not None:
            # Later steps consume the corrected file, not the original.
            produced[step.get("input_role", "")] = outcome.output_path
            produced[step.get("output_role", "")] = outcome.output_path
        else:
            failed_steps.add(outcome.step_id)

    return result


def assemble_package(
    outputs: dict[str, Path],
    originals: dict[str, Path],
    destination_id: str,
    rule_pack_digest: str,
    package_dir: Path,
) -> dict[str, Any]:
    """Build one destination package directory and its manifest.

    Repaired assets replace their originals; anything not repaired is carried
    across unchanged. Names are normalised through safe_package_name, which
    rejects traversal rather than quietly rewriting it.
    """
    package_dir.mkdir(parents=True, exist_ok=True)

    for role, path in {**originals, **outputs}.items():
        if path is None or not Path(path).exists():
            continue
        safe = repairs.safe_package_name(f"{destination_id}_{role}{Path(path).suffix}")
        shutil.copy2(path, package_dir / safe)

    return repairs.build_manifest(package_dir, destination_id, rule_pack_digest)


def temporary_workspace() -> tempfile.TemporaryDirectory:
    """Scratch space that is removed even when a job fails.

    Media workers hold other people's unreleased films; leaving copies on a
    container's disk after a crash is a disclosure risk, not untidiness.
    """
    return tempfile.TemporaryDirectory(prefix="preflight-job-")
