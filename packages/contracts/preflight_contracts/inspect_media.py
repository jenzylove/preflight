"""Deterministic measurement.

Every number Preflight asserts about a file is produced here, by a tool, with
its version recorded. Nothing in this module asks a model what a file contains.

Loudness in particular is measured with ffmpeg's EBU R128 implementation
(`ebur128` / `loudnorm`), not estimated, because loudness is the single most
common cause of delivery rejection and an estimate would be worse than silence.
"""

from __future__ import annotations

import json
import re
import shutil
import subprocess
from dataclasses import dataclass, field
from datetime import UTC, datetime
from fractions import Fraction
from pathlib import Path
from typing import Any

from .rules import AssetType

INSPECTOR_SCHEMA_VERSION = "1.0.0"


class InspectionError(RuntimeError):
    pass


@dataclass
class Evidence:
    """Measured properties plus the provenance of the measurement itself."""

    asset_type: AssetType
    inspector: str
    inspector_version: str
    measured_at: str
    properties: dict[str, Any] = field(default_factory=dict)
    schema_version: str = INSPECTOR_SCHEMA_VERSION

    def to_dict(self) -> dict[str, Any]:
        return {
            "assetType": self.asset_type.value,
            "inspector": self.inspector,
            "inspectorVersion": self.inspector_version,
            "measuredAt": self.measured_at,
            "schemaVersion": self.schema_version,
            "properties": self.properties,
        }


def _now() -> str:
    return datetime.now(UTC).isoformat(timespec="seconds")


def _require(tool: str) -> str:
    path = shutil.which(tool)
    if not path:
        raise InspectionError(f"{tool} is not installed or not on PATH")
    return path


def _run(args: list[str]) -> subprocess.CompletedProcess[str]:
    # Argument list, never a shell string: filenames are user-controlled.
    return subprocess.run(args, capture_output=True, text=True, check=False)


def tool_version(tool: str) -> str:
    _require(tool)
    out = _run([tool, "-version"]).stdout
    match = re.search(r"version (\S+)", out)
    return match.group(1) if match else "unknown"


# --------------------------------------------------------------------------
# Video / audio
# --------------------------------------------------------------------------

def probe(path: Path) -> dict[str, Any]:
    _require("ffprobe")
    proc = _run([
        "ffprobe", "-v", "error", "-print_format", "json",
        "-show_format", "-show_streams", str(path),
    ])
    if proc.returncode != 0:
        raise InspectionError(f"ffprobe failed on {path.name}: {proc.stderr.strip()[:200]}")
    return json.loads(proc.stdout)


#: ISO base-media brands that identify a file as MP4 rather than QuickTime.
_MP4_BRANDS = {"isom", "iso2", "mp41", "mp42", "avc1", "dash", "msdh", "mmp4", "M4V ", "M4A "}


def _container(fmt: dict[str, Any]) -> str | None:
    """Resolve the real container from the ISO base-media family.

    ffprobe reports a single shared demuxer name — ``mov,mp4,m4a,3gp,3g2,mj2`` —
    for every member of the family, so the first entry is meaningless. The
    ``major_brand`` in the ftyp box is what actually distinguishes an MP4 from a
    QuickTime file, and getting this wrong would invent a delivery failure that
    does not exist.
    """
    name = (fmt.get("format_name") or "").strip()
    if "," not in name:
        return name or None

    members = [m.strip() for m in name.split(",")]
    if "mp4" not in members:
        return members[0]

    brand = (fmt.get("tags") or {}).get("major_brand", "").strip()
    if brand in {b.strip() for b in _MP4_BRANDS}:
        return "mp4"
    if brand.startswith("qt"):
        return "mov"
    return "mp4" if brand else "mov"


def _frame_rate(stream: dict[str, Any]) -> float | None:
    raw = stream.get("avg_frame_rate") or stream.get("r_frame_rate")
    if not raw or raw == "0/0":
        return None
    return round(float(Fraction(raw)), 3)


def _display_aspect_ratio(stream: dict[str, Any]) -> str | None:
    dar = stream.get("display_aspect_ratio")
    if dar and dar != "0:1":
        return dar
    width, height = stream.get("width"), stream.get("height")
    if not width or not height:
        return None
    # Absent an explicit DAR flag, report the storage ratio and let the rule
    # engine decide — an unflagged file is exactly the failure we care about.
    ratio = Fraction(int(width), int(height)).limit_denominator(1000)
    return f"{ratio.numerator}:{ratio.denominator}"


def inspect_video(path: Path) -> Evidence:
    data = probe(path)
    fmt = data.get("format", {})
    streams = data.get("streams", [])
    video = next((s for s in streams if s.get("codec_type") == "video"), None)
    if video is None:
        raise InspectionError(f"{path.name} contains no video stream")

    has_faststart = _has_faststart(path)

    props: dict[str, Any] = {
        "container": _container(fmt),
        "codec": video.get("codec_name"),
        "profile": video.get("profile"),
        "widthPx": video.get("width"),
        "heightPx": video.get("height"),
        "frameRate": _frame_rate(video),
        "displayAspectRatio": _display_aspect_ratio(video),
        "bitrateBps": int(fmt["bit_rate"]) if fmt.get("bit_rate") else None,
        "durationSeconds": round(float(fmt["duration"]), 3) if fmt.get("duration") else None,
        "colourPrimaries": video.get("color_primaries"),
        "colourTransfer": video.get("color_transfer"),
        "colourMatrix": video.get("color_space"),
        "scanType": (
            "progressive"
            if video.get("field_order", "progressive") == "progressive"
            else "interlaced"
        ),
        "fastStart": has_faststart,
        # Recorded so the caller can prove the picture was left untouched.
        "videoStreamMd5": None,
    }
    return Evidence(AssetType.VIDEO, "ffprobe", tool_version("ffprobe"), _now(), props)


def _has_faststart(path: Path) -> bool:
    """True when the moov atom precedes mdat, i.e. the file streams immediately."""
    try:
        with path.open("rb") as handle:
            head = handle.read(2_000_000)
    except OSError:
        return False
    moov, mdat = head.find(b"moov"), head.find(b"mdat")
    if moov == -1:
        return False
    return mdat == -1 or moov < mdat


def video_stream_md5(path: Path) -> str:
    """Hash of the decoded picture only, ignoring container metadata.

    This is how Preflight proves a metadata repair did not touch the image:
    the container changes, this value does not.
    """
    _require("ffmpeg")
    proc = _run([
        "ffmpeg", "-v", "error", "-i", str(path),
        "-map", "0:v:0", "-c", "copy", "-f", "md5", "-",
    ])
    if proc.returncode != 0:
        raise InspectionError(f"video hash failed: {proc.stderr.strip()[:200]}")
    return proc.stdout.strip().removeprefix("MD5=")


def inspect_audio(path: Path) -> Evidence:
    """Measure audio properties including true EBU R128 integrated loudness."""
    data = probe(path)
    audio = next((s for s in data.get("streams", []) if s.get("codec_type") == "audio"), None)
    if audio is None:
        raise InspectionError(f"{path.name} contains no audio stream")

    loudness = measure_loudness(path)

    props: dict[str, Any] = {
        "codec": audio.get("codec_name"),
        "channels": audio.get("channels"),
        "sampleRateHz": int(audio["sample_rate"]) if audio.get("sample_rate") else None,
        "bitrateBps": int(audio["bit_rate"]) if audio.get("bit_rate") else None,
        **loudness,
    }
    return Evidence(AssetType.AUDIO, "ffmpeg/ebur128", tool_version("ffmpeg"), _now(), props)


def measure_loudness(path: Path) -> dict[str, float | None]:
    """First pass of the standard two-pass loudnorm workflow.

    Returns the file's actual integrated loudness, true peak and loudness range
    as measured by ffmpeg's EBU R128 implementation. These values are also the
    exact inputs the second pass needs, so measuring is never wasted work.
    """
    _require("ffmpeg")
    proc = _run([
        "ffmpeg", "-hide_banner", "-nostats", "-i", str(path),
        "-map", "0:a:0",
        "-af", "loudnorm=I=-23:TP=-2:LRA=7:print_format=json",
        "-f", "null", "-",
    ])
    match = re.search(r"\{[^{}]*\"input_i\"[^{}]*\}", proc.stderr, re.DOTALL)
    if not match:
        raise InspectionError(f"loudness measurement failed: {proc.stderr.strip()[-300:]}")

    stats = json.loads(match.group(0))

    def num(key: str) -> float | None:
        raw = stats.get(key)
        try:
            value = float(raw)
        except (TypeError, ValueError):
            return None
        # loudnorm reports -inf / -70 for silence; do not present that as a measurement.
        return None if value <= -70.0 else round(value, 2)

    return {
        "integratedLoudnessLufs": num("input_i"),
        "truePeakDbtp": num("input_tp"),
        "loudnessRangeLu": num("input_lra"),
        "_loudnormStats": stats,
    }


# --------------------------------------------------------------------------
# Subtitles
# --------------------------------------------------------------------------

_SRT_CUE = re.compile(r"^\d+\s*$\n^\d{2}:\d{2}:\d{2},\d{3}\s*-->", re.MULTILINE)
_VTT_CUE = re.compile(r"^\d{2}:\d{2}:\d{2}\.\d{3}\s*-->", re.MULTILINE)


def inspect_subtitle(path: Path) -> Evidence:
    raw = path.read_bytes()
    encoding = "utf-8-sig" if raw.startswith(b"\xef\xbb\xbf") else "utf-8"
    try:
        text = raw.decode(encoding)
    except UnicodeDecodeError as exc:
        raise InspectionError(f"{path.name} is not valid UTF-8 text") from exc

    if text.lstrip().startswith("WEBVTT"):
        fmt, cue_count = "vtt", len(_VTT_CUE.findall(text))
    elif _SRT_CUE.search(text):
        fmt, cue_count = "srt", len(_SRT_CUE.findall(text))
    else:
        raise InspectionError(f"{path.name} is neither SubRip nor WebVTT")

    props = {
        "format": fmt,
        "encoding": "utf-8-bom" if encoding == "utf-8-sig" else "utf-8",
        "cueCount": cue_count,
        "burnedIn": False,   # a sidecar file is by definition not burned in
        "language": None,
    }
    return Evidence(
        AssetType.SUBTITLE, "preflight.subtitles", INSPECTOR_SCHEMA_VERSION, _now(), props
    )


# --------------------------------------------------------------------------
# Poster
# --------------------------------------------------------------------------

def inspect_poster(path: Path) -> Evidence:
    import PIL
    from PIL import Image  # imported lazily so subtitle-only runs need no Pillow

    with Image.open(path) as image:
        width, height = image.size
        fmt = (image.format or "").lower()
        mode = image.mode

    ratio = Fraction(width, height).limit_denominator(100)
    props = {
        "format": "jpeg" if fmt in ("jpeg", "jpg") else fmt,
        "widthPx": width,
        "heightPx": height,
        "aspectRatio": f"{ratio.numerator}:{ratio.denominator}",
        "colourSpace": mode,
        "byteSize": path.stat().st_size,
    }
    return Evidence(AssetType.POSTER, "pillow", PIL.__version__, _now(), props)
