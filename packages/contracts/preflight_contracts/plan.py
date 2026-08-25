"""Repair planning.

A plan is a dependency graph over derived assets, and a digest over that graph.
The digest is the contract between the user and the worker: approval is granted
for one exact plan, and if any parameter of it changes the digest changes and
the approval no longer matches. That is what stops an approved "resize the
poster" from quietly becoming "re-encode the master".

Nothing here executes anything. Planning is pure — same inputs, same plan,
same digest — so a plan can be shown, stored, approved and compared without any
side effect.
"""

from __future__ import annotations

import hashlib
import json
from dataclasses import dataclass, field
from enum import Enum
from typing import Any

from .compare import Assertion, Result
from .rules import AssetType


class Safety(str, Enum):
    GREEN = "green"      # deterministic, non-creative, provably non-destructive
    YELLOW = "yellow"    # can alter quality, timing, framing or meaning
    RED = "red"          # needs authority or craft Preflight does not have


#: The complete set of operations the worker will execute, and what each one
#: costs in safety terms. An operation absent from this table cannot run —
#: the worker checks membership before doing anything.
OPERATION_CATALOGUE: dict[str, dict[str, Any]] = {
    "normalise_loudness": {
        "safety": Safety.GREEN,
        "input_role": "master",
        "output_role": "master_audio_corrected",
        "seconds_per_minute": 8,
        "explains": "Adjusts programme loudness by a single gain offset. "
                    "The mix is moved, not reshaped, and the picture is copied untouched.",
    },
    "rewrite_container_metadata": {
        "safety": Safety.GREEN,
        "input_role": "master",
        "output_role": "master_delivery",
        "seconds_per_minute": 2,
        "explains": "Corrects aspect ratio, colour signalling and fast-start flags. "
                    "Streams are copied, so the decoded picture is bit-identical.",
    },
    "convert_subtitles": {
        "safety": Safety.GREEN,
        "input_role": "subtitle",
        "output_role": "subtitle_delivery",
        "seconds_per_minute": 0,
        "explains": "Changes subtitle file format. Timings and text are carried "
                    "across unchanged; nothing is translated or retimed.",
    },
    "resize_poster": {
        "safety": Safety.GREEN,
        "input_role": "poster",
        "output_role": "poster_delivery",
        "seconds_per_minute": 0,
        "explains": "Scales artwork to fit the required frame and pads the "
                    "remainder. Nothing is cropped.",
    },
    "normalise_metadata": {
        "safety": Safety.GREEN,
        "input_role": "metadata",
        "output_role": "metadata_delivery",
        "seconds_per_minute": 0,
        "explains": "Reformats title, synopsis and language fields to the "
                    "destination's template.",
    },
    "rename_and_layout": {
        "safety": Safety.GREEN,
        "input_role": "package",
        "output_role": "package_layout",
        "seconds_per_minute": 0,
        "explains": "Applies the destination's file naming and folder structure.",
    },
    "build_manifest": {
        "safety": Safety.GREEN,
        "input_role": "package",
        "output_role": "package_manifest",
        "seconds_per_minute": 1,
        "explains": "Records a SHA-256 for every file in the package.",
    },
    # Planned and shown, never executed. Present so the user can see what
    # would be required and decide for themselves.
    "reencode_video": {
        "safety": Safety.YELLOW,
        "input_role": "master",
        "output_role": "master_reencoded",
        "seconds_per_minute": 45,
        "explains": "Re-encodes the picture to meet a bitrate, resolution or "
                    "codec requirement. This changes the image and cannot be undone.",
    },
    "crop_poster": {
        "safety": Safety.YELLOW,
        "input_role": "poster",
        "output_role": "poster_cropped",
        "seconds_per_minute": 0,
        "explains": "Crops artwork to a different aspect. Deciding what to remove "
                    "from key art is a creative choice, so Preflight will not make it.",
    },
    "translate_subtitles": {
        "safety": Safety.YELLOW,
        "input_role": "subtitle",
        "output_role": "subtitle_translated",
        "seconds_per_minute": 5,
        "explains": "Produces subtitles in another language. Requires human review "
                    "before delivery.",
    },
}


@dataclass(frozen=True)
class Step:
    step_id: str
    operation: str
    safety: Safety
    destination_id: str
    input_role: str
    output_role: str
    parameters: dict[str, Any]
    resolves: tuple[str, ...]          # rule ids this step satisfies
    depends_on: tuple[str, ...] = ()

    def fingerprint(self) -> str:
        """Everything that makes this step what it is."""
        return json.dumps(
            {
                "operation": self.operation,
                "destination": self.destination_id,
                "input": self.input_role,
                "output": self.output_role,
                "parameters": self.parameters,
                "dependsOn": sorted(self.depends_on),
            },
            sort_keys=True,
            separators=(",", ":"),
        )


@dataclass
class Plan:
    steps: list[Step] = field(default_factory=list)
    blocked: list[dict[str, Any]] = field(default_factory=list)
    unresolved: list[dict[str, Any]] = field(default_factory=list)
    reused: dict[str, list[str]] = field(default_factory=dict)

    @property
    def green(self) -> list[Step]:
        return [s for s in self.steps if s.safety is Safety.GREEN]

    @property
    def needs_decision(self) -> list[Step]:
        return [s for s in self.steps if s.safety is Safety.YELLOW]

    def digest(self) -> str:
        """Stable identity of the whole plan.

        Order-independent, so two runs that produce the same work in a
        different sequence approve the same thing.
        """
        payload = "|".join(sorted(s.fingerprint() for s in self.steps))
        return hashlib.sha256(payload.encode()).hexdigest()[:32]

    def estimated_seconds(self, runtime_seconds: int) -> int:
        minutes = max(1, runtime_seconds / 60)
        total = 0.0
        for step in self.green:
            rate = OPERATION_CATALOGUE[step.operation]["seconds_per_minute"]
            total += rate * minutes
        return int(total) + 5   # fixed overhead for fetch, hash and upload

    def preserved_assets(self, all_roles: set[str]) -> list[str]:
        """Inputs that no step touches — the reassurance that matters most.

        A producer's first question about any automated repair is what it will
        do to the parts they did not ask it to change.
        """
        touched = {s.input_role for s in self.green}
        return sorted(all_roles - touched)


def _poster_target(rules_by_field: dict[str, Any]) -> dict[str, int]:
    return {
        "width": int(rules_by_field.get("widthPx") or 1920),
        "height": int(rules_by_field.get("heightPx") or 1080),
    }


def build_plan(
    assertions_by_destination: dict[str, list[Assertion]],
    *,
    loudness_targets: dict[str, tuple[float, float]] | None = None,
    available_roles: set[str] | None = None,
) -> Plan:
    """Turn preflight results into an ordered, digest-bound repair plan.

    Steps are keyed by (operation, destination, parameters) so that two
    destinations needing identical work share one derived asset rather than
    producing it twice.
    """
    plan = Plan()
    loudness_targets = loudness_targets or {}
    counter = 0
    by_key: dict[str, Step] = {}

    for destination_id, assertions in assertions_by_destination.items():
        for assertion in assertions:
            if assertion.result is Result.PASS:
                continue

            if assertion.result is Result.NOT_APPLICABLE:
                continue

            if assertion.result is Result.AMBIGUOUS:
                plan.unresolved.append({
                    "destination": destination_id,
                    "field": f"{assertion.asset_type.value}.{assertion.field_name}",
                    "reason": assertion.explanation
                              or "Official sources state this requirement inconsistently.",
                    "needs": "your_confirmation",
                })
                continue

            if assertion.result is Result.NOT_MEASURED:
                plan.unresolved.append({
                    "destination": destination_id,
                    "field": f"{assertion.asset_type.value}.{assertion.field_name}",
                    "reason": "This property was not measured on the assets supplied.",
                    "needs": "missing_asset",
                })
                continue

            if assertion.result is Result.UNSUPPORTED:
                plan.blocked.append({
                    "destination": destination_id,
                    "field": f"{assertion.asset_type.value}.{assertion.field_name}",
                    "published": assertion.expected,
                    "measured": assertion.measured,
                    "reason": assertion.explanation,
                    "safety": Safety.RED.value,
                })
                continue

            operation = assertion.repair_operation or _yellow_operation(assertion)
            if operation is None:
                plan.blocked.append({
                    "destination": destination_id,
                    "field": f"{assertion.asset_type.value}.{assertion.field_name}",
                    "published": assertion.expected,
                    "measured": assertion.measured,
                    "reason": "No supported operation satisfies this requirement.",
                    "safety": Safety.RED.value,
                })
                continue

            spec = OPERATION_CATALOGUE[operation]
            parameters = _parameters_for(
                operation, assertion, destination_id, loudness_targets
            )

            if operation == "convert_subtitles" and not parameters.get("targetFormat"):
                # The requirement is real but states only what is unacceptable.
                # Converting requires knowing what to convert to.
                plan.unresolved.append({
                    "destination": destination_id,
                    "field": f"{assertion.asset_type.value}.{assertion.field_name}",
                    "reason": (
                        f"This destination states which subtitle formats it will not "
                        f"accept ({assertion.expected}) without naming one it will. "
                        f"Preflight will not guess a target format."
                    ),
                    "needs": "your_decision",
                })
                continue
            key = json.dumps(
                [operation, sorted(parameters.items(), key=str)], sort_keys=True, default=str
            )

            existing = by_key.get(key)
            if existing is not None:
                # Identical work for a second destination: reuse it.
                plan.reused.setdefault(existing.step_id, []).append(destination_id)
                merged = Step(
                    step_id=existing.step_id,
                    operation=existing.operation,
                    safety=existing.safety,
                    destination_id=existing.destination_id,
                    input_role=existing.input_role,
                    output_role=existing.output_role,
                    parameters=existing.parameters,
                    resolves=tuple(sorted(set(existing.resolves) | {assertion.rule_id})),
                    depends_on=existing.depends_on,
                )
                by_key[key] = merged
                plan.steps[plan.steps.index(existing)] = merged
                continue

            counter += 1
            step = Step(
                step_id=f"s{counter:02d}",
                operation=operation,
                safety=spec["safety"],
                destination_id=destination_id,
                input_role=spec["input_role"],
                output_role=spec["output_role"],
                parameters=parameters,
                resolves=(assertion.rule_id,),
            )
            by_key[key] = step
            plan.steps.append(step)

    plan.steps = _order(plan.steps)
    if available_roles:
        plan.reused = {k: sorted(set(v)) for k, v in plan.reused.items()}
    return plan


def _yellow_operation(assertion: Assertion) -> str | None:
    if assertion.result is not Result.REVIEW_REQUIRED:
        return None
    if assertion.asset_type is AssetType.VIDEO:
        return "reencode_video"
    if assertion.asset_type is AssetType.AUDIO:
        return "reencode_video"   # audio re-encode rides with the container rebuild
    if assertion.asset_type is AssetType.POSTER:
        return "crop_poster"
    if assertion.asset_type is AssetType.SUBTITLE:
        return "translate_subtitles"
    return None


#: Formats the subtitle converter can actually write.
_WRITABLE_SUBTITLE_FORMATS = ("srt", "vtt")


def _subtitle_target(expected: str) -> str | None:
    """Work out what format to convert to, or admit that we cannot.

    A requirement stated positively names the target: "eq srt", or "one of
    srt, vtt" where the first writable option wins. A requirement stated
    negatively - "not one of srt, sub, xml" - says only what is unacceptable.
    It cannot name a target, and inventing one from the forbidden list is how a
    converter ends up asked to write "xml, png, mxf" as if that were a format.

    Returning None means the failure is real but not automatically fixable,
    which is a better answer than a confident wrong one.
    """
    text = expected.strip().lower()

    if text.startswith("not one of") or text.startswith("neq "):
        return None

    if text.startswith("eq "):
        candidate = text.removeprefix("eq ").strip()
        return candidate if candidate in _WRITABLE_SUBTITLE_FORMATS else None

    if text.startswith("one of "):
        options = [o.strip() for o in text.removeprefix("one of ").split(",")]
        return next((o for o in options if o in _WRITABLE_SUBTITLE_FORMATS), None)

    return None


def _parameters_for(
    operation: str,
    assertion: Assertion,
    destination_id: str,
    loudness_targets: dict[str, tuple[float, float]],
) -> dict[str, Any]:
    if operation == "normalise_loudness":
        window = loudness_targets.get(destination_id)
        target = round(sum(window) / 2, 2) if window else -23.0
        return {"targetLufs": target, "truePeakDbtp": -3.0, "mode": "linear"}

    if operation == "rewrite_container_metadata":
        # Every metadata correction for one destination is one step, so the
        # container is rebuilt once rather than once per failing flag.
        return {"destination": destination_id, "corrects": "display_and_colour_signalling"}

    if operation == "convert_subtitles":
        target = _subtitle_target(assertion.expected)
        return {"targetFormat": target} if target else {}

    if operation == "resize_poster":
        return {"mode": "pad", "destination": destination_id}

    return {"destination": destination_id}


#: Metadata rewrite must follow loudness normalisation, because normalisation
#: produces the file whose container is then corrected.
_AFTER: dict[str, set[str]] = {
    "rewrite_container_metadata": {"normalise_loudness"},
    "build_manifest": {
        "normalise_loudness", "rewrite_container_metadata",
        "convert_subtitles", "resize_poster", "normalise_metadata",
        "rename_and_layout",
    },
    "rename_and_layout": {
        "normalise_loudness", "rewrite_container_metadata",
        "convert_subtitles", "resize_poster", "normalise_metadata",
    },
}


def _order(steps: list[Step]) -> list[Step]:
    """Resolve dependencies into a stable execution order."""
    by_operation: dict[str, list[Step]] = {}
    for step in steps:
        by_operation.setdefault(step.operation, []).append(step)

    resolved: list[Step] = []
    for step in steps:
        predecessors = tuple(
            sorted(
                other.step_id
                for operation in _AFTER.get(step.operation, set())
                for other in by_operation.get(operation, [])
                if other.step_id != step.step_id
            )
        )
        resolved.append(
            Step(
                step_id=step.step_id,
                operation=step.operation,
                safety=step.safety,
                destination_id=step.destination_id,
                input_role=step.input_role,
                output_role=step.output_role,
                parameters=step.parameters,
                resolves=step.resolves,
                depends_on=predecessors,
            )
        )

    order = list(_AFTER.keys())

    def rank(step: Step) -> int:
        return order.index(step.operation) + 1 if step.operation in order else 0

    return sorted(resolved, key=lambda s: (rank(s), s.step_id))


def approval_matches(plan_digest: str, approved_digest: str) -> bool:
    """AC-6. Constant-time is unnecessary here; exactness is not."""
    return bool(plan_digest) and plan_digest == approved_digest
