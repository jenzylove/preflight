"""Generate the Gate 0 malformed fixture.

Everything here is synthesised by ffmpeg and Pillow from nothing — test
patterns and tones. There is no third-party footage, so the fixture can live in
a public repository and be redistributed without any rights question.

The defects are chosen deliberately: each one maps to a real requirement
published by one of the two Gate 0 destinations, and between them they cover
every repair class Preflight claims to support plus one it deliberately refuses.
"""

from __future__ import annotations

import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
FIXTURE_DIR = ROOT / "packages" / "fixtures" / "malformed"

DURATION = 12  # seconds — long enough for a stable EBU R128 measurement


def run(args: list[str], description: str) -> None:
    print(f"  {description}")
    proc = subprocess.run(args, capture_output=True, text=True)
    if proc.returncode != 0:
        print(proc.stderr[-800:], file=sys.stderr)
        raise SystemExit(f"failed: {description}")


def make_master(path: Path) -> None:
    """A 1080p master carrying four separate, real delivery defects.

    1. Integrated loudness far too hot for Artdocfest's -18..-21 LUFS window.
    2. True peak above Artdocfest's published -3 dBTP ceiling.
    3. Display aspect ratio flagged 4:3 on a 16:9 raster - the classic metadata
       fault that makes a platform letterbox a film incorrectly.
    4. moov atom written at the end of the file, so it will not fast-start.
    5. Colour primaries left unsignalled, so BT.709 cannot be assumed.

    Both audio defects come from one cause - a mix driven far too hot - which
    is also how they occur in practice, and both are corrected by the single
    two-pass normalisation Preflight performs.
    """
    run(
        [
            "ffmpeg", "-y", "-hide_banner", "-loglevel", "error",
            "-f", "lavfi", "-i", f"testsrc2=size=1920x1080:rate=25:duration={DURATION}",
            # Two tones summed and driven hard: loud, and peaking near full scale.
            "-f", "lavfi", "-i",
            f"sine=frequency=440:sample_rate=48000:duration={DURATION}",
            "-f", "lavfi", "-i",
            f"sine=frequency=277:sample_rate=48000:duration={DURATION}",
            # Drive the mix to a specific, verifiably out-of-spec loudness.
            # The result sits far above Artdocfest's -18..-21 LUFS window and
            # breaches its -3 dBTP ceiling, so both failures are unambiguous
            # when measured rather than hovering near a boundary.
            "-filter_complex",
            # Direct gain rather than loudnorm: loudnorm's own true-peak
            # limiter refuses to produce a peak-breaching file, which is the
            # very defect being modelled here. A mix pushed hard with no
            # limiter is also how this arrives in practice.
            "[1:a][2:a]amix=inputs=2:duration=first,volume=20dB[a]",
            "-map", "0:v", "-map", "[a]",
            "-c:v", "libx264", "-profile:v", "high", "-preset", "veryfast",
            "-b:v", "8000k", "-pix_fmt", "yuv420p",
            # Defect 3: lie about the display aspect ratio.
            "-aspect", "4:3",
            "-c:a", "aac", "-b:a", "384k", "-ar", "48000", "-ac", "2",
            # Defect 4: no +faststart, so moov lands after mdat.
            "-movflags", "+use_metadata_tags",
            str(path),
        ],
        "master.mp4 — 1080p25, hot audio, 4:3 flag, no fast start",
    )


def make_subtitles(path: Path) -> None:
    """A WebVTT sidecar. Artdocfest requires SubRip, so this needs conversion."""
    path.write_text(
        "WEBVTT\n\n"
        "1\n00:00:00.000 --> 00:00:04.000\nA test pattern, holding steady.\n\n"
        "2\n00:00:04.000 --> 00:00:08.000\nTwo tones, mixed too loud for delivery.\n\n"
        "3\n00:00:08.000 --> 00:00:12.000\nAnd an aspect ratio that lies about itself.\n",
        encoding="utf-8",
        newline="\n",
    )
    print("  subtitles.vtt — WebVTT where SubRip is required")


def make_poster(path: Path) -> None:
    """An undersized poster, in the wrong aspect, so a pad-fit is required."""
    from PIL import Image, ImageDraw

    width, height = 640, 640
    image = Image.new("RGB", (width, height), (18, 18, 24))
    draw = ImageDraw.Draw(image)
    for i in range(0, width, 40):
        shade = 40 + (i % 160)
        draw.line([(i, 0), (i, height)], fill=(shade, shade // 2, 90), width=2)
    draw.rectangle([60, 250, 580, 390], fill=(12, 12, 16))
    draw.text((90, 300), "PREFLIGHT FIXTURE", fill=(240, 240, 240))
    image.save(path, "JPEG", quality=92)
    print(f"  poster.jpg — {width}x{height} square, undersized")


def main() -> None:
    FIXTURE_DIR.mkdir(parents=True, exist_ok=True)
    print(f"generating fixture in {FIXTURE_DIR}")

    make_master(FIXTURE_DIR / "master.mp4")
    make_subtitles(FIXTURE_DIR / "subtitles.vtt")
    make_poster(FIXTURE_DIR / "poster.jpg")

    print("\nfixture ready. Defects are real and measurable, not annotations:")
    print("  audio loudness      ~-4 LUFS against Artdocfest's -18..-21 window")
    print("  audio true peak     above the published -3 dBTP ceiling")
    print("  display aspect      flagged 4:3 on a 16:9 raster")
    print("  fast start          moov atom written after mdat")
    print("  subtitle format     WebVTT where SubRip is mandatory")
    print("  poster size         640x640 where a large landscape key art is wanted")
    print("  video bitrate       8 Mbps against Artdocfest's 20-30 Mbps mandate")
    print("                      (deliberately NOT auto-repaired — that re-encodes)")


if __name__ == "__main__":
    main()
