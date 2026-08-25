"""Gate 0: prove the central transaction end to end, with scripts only.

    measure the real file
      -> compare against real published rules
      -> repair what is safely repairable
      -> measure the outputs independently
      -> report

The gate passes only if the revalidation is done against the *outputs*, and only
if every claim in the report traces to either a tool measurement or a cited
source. No interface is built until this holds.
"""

from __future__ import annotations

import sys as _sys

# Windows consoles default to cp1252. A report that crashes while
# printing a citation is worse than no report.
if hasattr(_sys.stdout, "reconfigure"):
    _sys.stdout.reconfigure(encoding="utf-8", errors="replace")

import json
import shutil
import sys
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "packages" / "contracts"))
sys.path.insert(0, str(Path(__file__).resolve().parent))

from preflight_contracts import inspect_media as inspector  # noqa: E402
from preflight_contracts import repairs  # noqa: E402
from preflight_contracts.compare import (  # noqa: E402
    Result,
    comparison_digest,
    evaluate_pack,
    find_conflicts,
    is_ready,
)
from preflight_contracts.rules import AssetType, RulePack  # noqa: E402
from seed_rule_packs import ARTDOCFEST, BERLINALE  # noqa: E402

FIXTURE = ROOT / "packages" / "fixtures" / "malformed"
WORK = ROOT / "out" / "gate0"

SYMBOL = {
    Result.PASS: "PASS  ",
    Result.REPAIRABLE: "REPAIR",
    Result.REVIEW_REQUIRED: "REVIEW",
    Result.UNSUPPORTED: "BLOCK ",
    Result.AMBIGUOUS: "AMBIG ",
    Result.NOT_MEASURED: "UNMEAS",
    Result.NOT_APPLICABLE: "N/A   ",
}


def measure(master: Path, subtitle: Path, poster: Path) -> dict[AssetType, dict[str, Any]]:
    video = inspector.inspect_video(master)
    audio = inspector.inspect_audio(master)
    subs = inspector.inspect_subtitle(subtitle)
    art = inspector.inspect_poster(poster)
    return {
        AssetType.VIDEO: video.properties,
        AssetType.AUDIO: audio.properties,
        AssetType.SUBTITLE: subs.properties,
        AssetType.POSTER: art.properties,
    }


def print_matrix(title: str, packs: list[RulePack], measured) -> dict[str, list]:
    print(f"\n{'=' * 78}\n{title}\n{'=' * 78}")
    all_assertions = {}
    for pack in packs:
        assertions = evaluate_pack(pack, measured)
        all_assertions[pack.destination_id] = assertions
        failing = [a for a in assertions if a.result is not Result.PASS]
        print(f"\n  {pack.destination_id}  (rule pack v{pack.version}, digest {pack.digest()})")
        print(f"  {len(assertions) - len(failing)}/{len(assertions)} rules satisfied"
              f"   ready={is_ready(assertions)}")
        for a in assertions:
            if a.result is Result.PASS:
                continue
            print(f"    {SYMBOL[a.result]}  {a.asset_type.value}.{a.field_name}")
            print(f"              published: {a.expected}")
            print(f"              measured:  {a.measured}")
            if a.repair_operation:
                print(f"              fix:       {a.repair_operation}")
    return all_assertions


def main() -> int:
    master = FIXTURE / "master.mp4"
    subtitle = FIXTURE / "subtitles.vtt"
    poster = FIXTURE / "poster.jpg"
    if not master.exists():
        raise SystemExit("fixture missing - run scripts/gate0/make_fixture.py first")

    if WORK.exists():
        shutil.rmtree(WORK)
    WORK.mkdir(parents=True)

    packs = [BERLINALE, ARTDOCFEST]

    # ---- 1. Measure the original ------------------------------------------
    print("measuring the master with deterministic tools")
    original_sha = repairs.sha256_file(master)
    original_picture = inspector.video_stream_md5(master)
    measured = measure(master, subtitle, poster)

    print(f"  ffprobe {inspector.tool_version('ffprobe')}, "
          f"ffmpeg {inspector.tool_version('ffmpeg')}")
    print(f"  master sha256        {original_sha[:32]}...")
    print(f"  picture md5          {original_picture}")
    print(f"  integrated loudness  {measured[AssetType.AUDIO]['integratedLoudnessLufs']} LUFS")
    print(f"  true peak            {measured[AssetType.AUDIO]['truePeakDbtp']} dBTP")
    print(f"  display aspect       {measured[AssetType.VIDEO]['displayAspectRatio']}")
    print(f"  fast start           {measured[AssetType.VIDEO]['fastStart']}")

    before = print_matrix("BEFORE REPAIR", packs, measured)
    before_digest = comparison_digest([a for v in before.values() for a in v])

    failures = [a for v in before.values() for a in v if a.result is not Result.PASS]
    repairable = [a for a in failures if a.result is Result.REPAIRABLE]
    print(f"\n  {len(failures)} mismatches detected, {len(repairable)} safely repairable")

    # ---- 2. Cross-destination conflicts -----------------------------------
    conflicts = find_conflicts(packs)
    if conflicts:
        print(f"\n{'=' * 78}\nCROSS-DESTINATION CONFLICTS\n{'=' * 78}")
        for c in conflicts:
            print(f"  [{c['strength'].upper()}] {c['assetType']}.{c['field']}: "
                  f"{c['destinations'][0]} wants {c['requirements'][0]}, "
                  f"{c['destinations'][1]} wants {c['requirements'][1]}")
            print(f"           -> {c['resolution']}")

    # ---- 3. Repair --------------------------------------------------------
    print(f"\n{'=' * 78}\nREPAIR (green operations only)\n{'=' * 78}")
    performed: list[repairs.RepairResult] = []

    # Loudness, to the midpoint of Artdocfest's published window.
    target = sum(ARTDOCFEST_LOUDNESS_WINDOW) / 2
    loud_out = WORK / "master_loudness.mp4"
    performed.append(repairs.normalise_loudness(master, loud_out, target_lufs=target,
                                                true_peak_dbtp=-3.0))
    print(f"  normalise_loudness       -> {target} LUFS target")

    # Aspect ratio, colour signalling and fast start, without re-encoding.
    fixed_master = WORK / "master_delivery.mp4"
    performed.append(repairs.rewrite_container_metadata(
        loud_out, fixed_master, display_aspect_ratio="16:9",
        colour_primaries="bt709", colour_transfer="bt709", colour_matrix="bt709",
        fast_start=True,
    ))
    print("  rewrite_container_metadata -> 16:9, BT.709, fast start")

    srt_out = WORK / "subtitles.srt"
    performed.append(repairs.convert_subtitles(subtitle, srt_out, "srt"))
    print("  convert_subtitles        -> SubRip")

    poster_out = WORK / "poster.jpg"
    performed.append(repairs.resize_poster(poster, poster_out, 1920, 1080, mode="pad"))
    print("  resize_poster            -> 1920x1080, padded, not cropped")

    # ---- 4. Independent revalidation, per destination ---------------------
    #
    # Each destination is validated against the assets it would actually
    # receive. A shared output set is wrong whenever destinations conflict:
    # converting subtitles to SubRip satisfies Artdocfest and simultaneously
    # violates Berlinale, which rejects sidecar files outright. Measuring one
    # shared set would report a repair as a regression, or hide it.
    print("")
    print("=" * 78)
    print("INDEPENDENT REVALIDATION (per destination, measuring outputs)")
    print("=" * 78)

    delivered = {
        # Artdocfest: SubRip sidecar, burned-in not allowed.
        "artdocfest": (fixed_master, srt_out, poster_out),
        # Berlinale: the original WebVTT is no more acceptable than SubRip —
        # both are sidecars, and Berlinale requires the subtitles to be burned
        # into the picture. That is a yellow operation, so Preflight cannot
        # satisfy it and says so instead of shipping something that will fail.
        "berlinale": (fixed_master, subtitle, poster_out),
    }

    after: dict[str, list] = {}
    for pack in packs:
        master_p, subs_p, poster_p = delivered[pack.destination_id]
        measured_for_destination = measure(master_p, subs_p, poster_p)
        assertions = evaluate_pack(pack, measured_for_destination)
        after[pack.destination_id] = assertions

        failing = [a for a in assertions if a.result is not Result.PASS]
        print("")
        print(f"  {pack.destination_id}  "
              f"{len(assertions) - len(failing)}/{len(assertions)} satisfied   "
              f"ready={is_ready(assertions)}")
        for a in failing:
            print(f"    {SYMBOL[a.result]}  {a.asset_type.value}.{a.field_name}")
            print(f"              published: {a.expected}")
            print(f"              measured:  {a.measured}")

    after_digest = comparison_digest([a for v in after.values() for a in v])

    # ---- 5. Integrity proofs ----------------------------------------------
    print(f"\n{'=' * 78}\nINTEGRITY\n{'=' * 78}")
    still_sha = repairs.sha256_file(master)
    still_picture = inspector.video_stream_md5(master)
    picture_after = inspector.video_stream_md5(fixed_master)

    original_untouched = still_sha == original_sha
    metadata_only = picture_after == original_picture

    print(f"  original sha256 unchanged        {original_untouched}")
    print(f"  original picture md5 unchanged   {still_picture == original_picture}")
    print(f"  repaired picture identical to original   {metadata_only}")
    print(f"    original {original_picture}")
    print(f"    repaired {picture_after}")
    print(f"  comparison digest before/after   {before_digest} -> {after_digest}")

    # ---- 6. Report --------------------------------------------------------
    report = {
        "fixture": {"master": master.name, "sha256": original_sha, "pictureMd5": original_picture},
        "tools": {
            "ffprobe": inspector.tool_version("ffprobe"),
            "ffmpeg": inspector.tool_version("ffmpeg"),
        },
        "rulePacks": [
            {"destinationId": p.destination_id, "version": p.version, "digest": p.digest(),
             "rules": len(p.rules), "required": len(p.required_rules()),
             "sources": sorted({e.url for e in p.evidence.values()})}
            for p in packs
        ],
        "conflicts": conflicts,
        "before": {d: [_assertion_json(a) for a in v] for d, v in before.items()},
        "repairs": [r.to_dict() for r in performed],
        "after": {d: [_assertion_json(a) for a in v] for d, v in after.items()},
        "integrity": {
            "originalUnchanged": original_untouched,
            "repairedPictureIdenticalToOriginal": metadata_only,
            "comparisonDigestBefore": before_digest,
            "comparisonDigestAfter": after_digest,
        },
    }
    report_path = WORK / "gate0_report.json"
    report_path.write_text(json.dumps(report, indent=2, default=str), encoding="utf-8")

    # ---- 7. Gate decision --------------------------------------------------
    fixed = 0
    for destination_id, before_assertions in before.items():
        was = {a.rule_id for a in before_assertions if a.result is not Result.PASS}
        now = {a.rule_id for a in after[destination_id] if a.result is not Result.PASS}
        fixed += len(was - now)
    checks = {
        "at least four real mismatches detected": len(failures) >= 4,
        "at least four safe repairs executed": len(performed) >= 4,
        # Three, not four. The ceiling is set by what these two destinations
        # actually publish: Berlinale states no aspect-ratio or fast-start
        # requirement, so the container rewrite - which still runs, and is
        # still proven non-destructive - resolves no published rule for this
        # pair. Demanding four would mean either inventing a requirement or
        # picking destinations to flatter the number.
        "at least three published requirements resolved": fixed >= 3,
        "original asset unchanged": original_untouched,
        "picture preserved through metadata repair": metadata_only,
        "a cross-destination conflict was found": bool(conflicts),
        "every rule traces to a cited source": all(
            r.source_evidence_id in p.evidence for p in packs for r in p.rules
        ),
    }
    print(f"\n{'=' * 78}\nGATE 0 DECISION\n{'=' * 78}")
    for label, ok in checks.items():
        print(f"  [{'x' if ok else ' '}] {label}")
    print(f"\n  report: {report_path}")

    if all(checks.values()):
        print("\n  GATE 0 PASSES - the central transaction works on real files "
              "against real published rules.")
        return 0
    print("\n  GATE 0 FAILS - do not proceed to Gate 1.")
    return 1


ARTDOCFEST_LOUDNESS_WINDOW = (-21.0, -18.0)


def _assertion_json(a) -> dict[str, Any]:
    return {
        "ruleId": a.rule_id,
        "assetType": a.asset_type.value,
        "field": a.field_name,
        "expected": a.expected,
        "measured": a.measured,
        "result": a.result.value,
        "severity": a.severity.value,
        "sourceEvidenceId": a.source_evidence_id,
        "repairOperation": a.repair_operation,
    }


if __name__ == "__main__":
    raise SystemExit(main())
