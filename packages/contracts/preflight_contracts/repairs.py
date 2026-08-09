"""Green repair operations.

Green means: deterministic, non-creative, and provably non-destructive to the
picture. Every operation here writes a *new* file and never touches its input.

The two operations that matter most are the two that address real delivery
rejections:

  * ``normalise_loudness`` — a proper two-pass EBU R128 loudnorm. The first pass
    measures; the second pass applies a single linear correction using those
    measurements. Linear mode applies one gain offset to the whole programme, so
    the mix's internal dynamics are preserved. This is not a remix.

  * ``rewrite_container_metadata`` — fixes aspect-ratio flags, colour tags and
    fast-start with ``-c copy``. Streams are remuxed, never re-encoded, so the
    decoded picture is bit-identical. ``verify_picture_unchanged`` proves it.
"""

from __future__ import annotations

import hashlib
import json
import re
import shutil
import subprocess
from dataclasses import dataclass
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

from .inspect_media import InspectionError, measure_loudness, video_stream_md5


class RepairError(RuntimeError):
    pass


@dataclass
class RepairResult:
    operation: str
    input_path: Path
    output_path: Path
    parameters: dict[str, Any]
    input_sha256: str
    output_sha256: str
    picture_preserved: bool | None
    performed_at: str

    def to_dict(self) -> dict[str, Any]:
        return {
            "operation": self.operation,
            "input": self.input_path.name,
            "output": self.output_path.name,
            "parameters": self.parameters,
            "inputSha256": self.input_sha256,
            "outputSha256": self.output_sha256,
            "picturePreserved": self.picture_preserved,
            "performedAt": self.performed_at,
        }


def sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def _now() -> str:
    return datetime.now(UTC).isoformat(timespec="seconds")


def _run(args: list[str]) -> subprocess.CompletedProcess[str]:
    if not shutil.which(args[0]):
        raise RepairError(f"{args[0]} is not installed or not on PATH")
    return subprocess.run(args, capture_output=True, text=True, check=False)


def _guard(source: Path, output: Path) -> None:
    """The original is immutable. Refuse any operation that would overwrite it."""
    if output.resolve() == source.resolve():
        raise RepairError("refusing to write over the original asset")
    output.parent.mkdir(parents=True, exist_ok=True)


# ---------------------------------------------------------------------------
# Audio loudness
# ---------------------------------------------------------------------------

def normalise_loudness(
    source: Path,
    output: Path,
    target_lufs: float,
    true_peak_dbtp: float = -3.0,
    loudness_range_lu: float = 11.0,
) -> RepairResult:
    """Two-pass EBU R128 normalisation to a destination's published target.

    Pass one measures the programme. Pass two feeds those measurements back to
    loudnorm in linear mode, which applies a single gain offset rather than
    dynamic compression — the mix is moved, not reshaped.
    """
    _guard(source, output)

    measured = measure_loudness(source)
    stats = measured["_loudnormStats"]
    if measured["integratedLoudnessLufs"] is None:
        raise RepairError(
            "cannot normalise: no measurable programme loudness (is the audio silent?)"
        )

    loudnorm = (
        f"loudnorm=I={target_lufs}:TP={true_peak_dbtp}:LRA={loudness_range_lu}"
        f":measured_I={stats['input_i']}:measured_TP={stats['input_tp']}"
        f":measured_LRA={stats['input_lra']}:measured_thresh={stats['input_thresh']}"
        f":offset={stats.get('target_offset', 0)}:linear=true:print_format=json"
    )

    proc = _run([
        "ffmpeg", "-y", "-hide_banner", "-nostats", "-i", str(source),
        "-map", "0:v?", "-c:v", "copy",          # picture passes through untouched
        "-map", "0:a", "-af", loudnorm,
        "-c:a", "aac", "-b:a", "384k", "-ar", "48000",
        "-movflags", "+faststart",
        str(output),
    ])
    if proc.returncode != 0:
        raise RepairError(f"loudness normalisation failed: {proc.stderr.strip()[-300:]}")

    picture_preserved = _picture_matches(source, output)

    return RepairResult(
        operation="normalise_loudness",
        input_path=source,
        output_path=output,
        parameters={
            "targetLufs": target_lufs,
            "truePeakDbtp": true_peak_dbtp,
            "measuredInLufs": measured["integratedLoudnessLufs"],
            "measuredInTruePeakDbtp": measured["truePeakDbtp"],
            "mode": "linear",
        },
        input_sha256=sha256_file(source),
        output_sha256=sha256_file(output),
        picture_preserved=picture_preserved,
        performed_at=_now(),
    )


# ---------------------------------------------------------------------------
# Container / display metadata
# ---------------------------------------------------------------------------

def rewrite_container_metadata(
    source: Path,
    output: Path,
    display_aspect_ratio: str | None = None,
    colour_primaries: str | None = None,
    colour_transfer: str | None = None,
    colour_matrix: str | None = None,
    fast_start: bool = True,
) -> RepairResult:
    """Correct display and colour signalling without re-encoding anything."""
    _guard(source, output)

    args = ["ffmpeg", "-y", "-hide_banner", "-nostats", "-i", str(source), "-c", "copy"]

    if display_aspect_ratio:
        if not re.fullmatch(r"\d{1,5}:\d{1,5}", display_aspect_ratio):
            raise RepairError(f"invalid display aspect ratio {display_aspect_ratio!r}")
        args += ["-aspect", display_aspect_ratio]
    if colour_primaries:
        args += ["-color_primaries", colour_primaries]
    if colour_transfer:
        args += ["-color_trc", colour_transfer]
    if colour_matrix:
        args += ["-colorspace", colour_matrix]
    if fast_start:
        args += ["-movflags", "+faststart"]

    args.append(str(output))

    proc = _run(args)
    if proc.returncode != 0:
        raise RepairError(f"container metadata rewrite failed: {proc.stderr.strip()[-300:]}")

    picture_preserved = _picture_matches(source, output)
    if picture_preserved is False:
        raise RepairError(
            "container rewrite altered the picture — refusing to return this output. "
            "This operation is only safe if the video stream is copied verbatim."
        )

    return RepairResult(
        operation="rewrite_container_metadata",
        input_path=source,
        output_path=output,
        parameters={
            "displayAspectRatio": display_aspect_ratio,
            "colourPrimaries": colour_primaries,
            "colourTransfer": colour_transfer,
            "colourMatrix": colour_matrix,
            "fastStart": fast_start,
        },
        input_sha256=sha256_file(source),
        output_sha256=sha256_file(output),
        picture_preserved=picture_preserved,
        performed_at=_now(),
    )


def _picture_matches(source: Path, output: Path) -> bool | None:
    """Compare decoded video streams. None when either file has no picture."""
    try:
        return video_stream_md5(source) == video_stream_md5(output)
    except (InspectionError, RepairError):
        return None


# ---------------------------------------------------------------------------
# Subtitles
# ---------------------------------------------------------------------------

_SRT_TIME = re.compile(
    r"(\d{2}:\d{2}:\d{2}),(\d{3})\s*-->\s*(\d{2}:\d{2}:\d{2}),(\d{3})"
)
_VTT_TIME = re.compile(
    r"(\d{2}:\d{2}:\d{2})\.(\d{3})\s*-->\s*(\d{2}:\d{2}:\d{2})\.(\d{3})"
)


def convert_subtitles(source: Path, output: Path, target_format: str) -> RepairResult:
    """SRT ⇄ WebVTT. Timings and text are carried across unchanged.

    Nothing is translated, retimed or reworded — only the container syntax
    changes, which is what makes this a green operation.
    """
    _guard(source, output)
    target = target_format.lower().lstrip(".")
    if target not in ("srt", "vtt"):
        raise RepairError(f"unsupported subtitle target format {target_format!r}")

    text = source.read_text(encoding="utf-8-sig")
    is_vtt = text.lstrip().startswith("WEBVTT")

    if target == "vtt":
        if is_vtt:
            body = text
        else:
            converted = _SRT_TIME.sub(r"\1.\2 --> \3.\4", text)
            # SubRip cue numbers are not valid WebVTT cue identifiers to keep,
            # but WebVTT tolerates them as identifiers, so they are preserved.
            body = "WEBVTT\n\n" + converted.lstrip()
    else:
        if not is_vtt:
            body = text
        else:
            stripped = re.sub(r"^WEBVTT.*?\n\n", "", text.lstrip(), count=1, flags=re.DOTALL)
            stripped = re.sub(r"^(NOTE|STYLE|REGION)\b.*?(\n\n|\Z)", "", stripped,
                              flags=re.DOTALL | re.MULTILINE)
            converted = _VTT_TIME.sub(r"\1,\2 --> \3,\4", stripped)
            body = _renumber_srt(converted)

    if not body.endswith("\n"):
        body += "\n"
    output.write_text(body, encoding="utf-8", newline="\n")

    return RepairResult(
        operation="convert_subtitles",
        input_path=source,
        output_path=output,
        parameters={"from": "vtt" if is_vtt else "srt", "to": target},
        input_sha256=sha256_file(source),
        output_sha256=sha256_file(output),
        picture_preserved=None,
        performed_at=_now(),
    )


def _renumber_srt(text: str) -> str:
    """SubRip requires sequential cue numbers; WebVTT cues may have none."""
    blocks = [b for b in re.split(r"\n{2,}", text.strip()) if b.strip()]
    out: list[str] = []
    for index, block in enumerate(blocks, start=1):
        lines = block.strip().split("\n")
        if lines and not _SRT_TIME.search(lines[0]):
            lines = lines[1:]  # drop any pre-existing identifier line
        out.append(f"{index}\n" + "\n".join(lines))
    return "\n\n".join(out) + "\n"


# ---------------------------------------------------------------------------
# Poster
# ---------------------------------------------------------------------------

def resize_poster(
    source: Path,
    output: Path,
    width: int,
    height: int,
    mode: str = "pad",
    background: tuple[int, int, int] = (0, 0, 0),
) -> RepairResult:
    """Fit the artwork into the target frame without cropping it.

    ``pad`` is the default and the only green mode: the image is scaled to fit
    entirely inside the target and the remainder is filled. Cropping is a
    creative decision about what to remove from someone's key art, so it stays
    yellow and is never performed automatically.
    """
    from PIL import Image

    _guard(source, output)
    if mode != "pad":
        raise RepairError(f"mode {mode!r} is not a green operation; only 'pad' is automatic")

    with Image.open(source) as image:
        original_size = image.size
        image = image.convert("RGB")
        scale = min(width / image.width, height / image.height)
        new_size = (max(1, round(image.width * scale)), max(1, round(image.height * scale)))
        resized = image.resize(new_size, Image.LANCZOS)

        canvas = Image.new("RGB", (width, height), background)
        canvas.paste(resized, ((width - new_size[0]) // 2, (height - new_size[1]) // 2))

        suffix = output.suffix.lower()
        fmt = "JPEG" if suffix in (".jpg", ".jpeg") else "PNG"
        save_kwargs = {"quality": 95, "subsampling": 0} if fmt == "JPEG" else {}
        canvas.save(output, fmt, **save_kwargs)

    return RepairResult(
        operation="resize_poster",
        input_path=source,
        output_path=output,
        parameters={
            "from": f"{original_size[0]}x{original_size[1]}",
            "to": f"{width}x{height}",
            "mode": mode,
            "cropped": False,
        },
        input_sha256=sha256_file(source),
        output_sha256=sha256_file(output),
        picture_preserved=None,
        performed_at=_now(),
    )


# ---------------------------------------------------------------------------
# Package manifest
# ---------------------------------------------------------------------------

def build_manifest(package_dir: Path, destination_id: str, rule_pack_digest: str) -> dict[str, Any]:
    """SHA-256 manifest over a package directory, with stable ordering.

    Ordering is sorted by relative POSIX path so the manifest — and therefore
    its digest — is reproducible regardless of filesystem enumeration order.
    """
    files = sorted(
        (p for p in package_dir.rglob("*") if p.is_file() and p.name != "manifest.json"),
        key=lambda p: p.relative_to(package_dir).as_posix(),
    )
    entries = [
        {
            "path": p.relative_to(package_dir).as_posix(),
            "sha256": sha256_file(p),
            "byteSize": p.stat().st_size,
        }
        for p in files
    ]
    manifest = {
        "destinationId": destination_id,
        "rulePackDigest": rule_pack_digest,
        "checksumAlgorithm": "sha256",
        "createdAt": _now(),
        "files": entries,
    }
    manifest["manifestDigest"] = hashlib.sha256(
        json.dumps(entries, sort_keys=True, separators=(",", ":")).encode()
    ).hexdigest()[:16]

    (package_dir / "manifest.json").write_text(
        json.dumps(manifest, indent=2), encoding="utf-8"
    )
    return manifest


def safe_package_name(name: str) -> str:
    """Normalise a filename for archive inclusion.

    Rejects traversal and absolute paths outright rather than sanitising them
    quietly — a filename containing ``..`` is a signal, not a typo.
    """
    if "\x00" in name:
        raise RepairError("filename contains a null byte")
    candidate = name.replace("\\", "/").strip()
    if candidate.startswith("/") or re.match(r"^[A-Za-z]:", candidate):
        raise RepairError(f"absolute path rejected: {name!r}")
    if any(part == ".." for part in candidate.split("/")):
        raise RepairError(f"path traversal rejected: {name!r}")
    cleaned = re.sub(r"[^A-Za-z0-9._/-]", "_", candidate)
    return re.sub(r"_{2,}", "_", cleaned).strip("_/")
