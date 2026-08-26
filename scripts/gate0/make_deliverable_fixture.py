"""A master built to be deliverable to Artdocfest, not to flatter Preflight.

The Gate 0 fixture is deliberately broken, which proves detection but can never
prove delivery. This one is what a producer would actually hand over, with two
faults left in that Preflight is allowed to correct:

  * loudness outside the published -18..-21 LUFS window
  * WebVTT subtitles where SubRip is required

Everything else is built to the published specification from the start, because
that is what a finished master looks like. Nothing here is chosen to dodge a
check: the resolution, frame rate, codec and bitrate are the FullHD row of
Artdocfest's own table, and the audio is AC-3 at 320 kbit/s because the
specification names AC-3 and "from 320 kbit/s".

The audio is deliberately dynamic. Artdocfest asks for 25-30 dB of dynamic
range, and a steady tone has none - a fixture that ignored that would pass a
check the real requirement would fail.
"""

from __future__ import annotations

import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
FIXTURE_DIR = ROOT / "packages" / "fixtures" / "deliverable"

DURATION = 24          # one full staircase cycle, kept short enough to upload
WIDTH, HEIGHT = 1920, 1080
FRAME_RATE = 25
VIDEO_BITRATE = "24M"  # inside the published 20-30 Mbps FullHD window


def run(args: list[str], description: str) -> None:
    print(f"  {description}")
    proc = subprocess.run(args, capture_output=True, text=True)
    if proc.returncode != 0:
        print(proc.stderr[-900:], file=sys.stderr)
        raise SystemExit(f"failed: {description}")


def make_master(path: Path) -> None:
    """FullHD H.264 at 24 Mbps with dynamic AC-3 audio, mixed too hot.

    The audio alternates between a quiet passage and a loud one so it has real
    loudness range. Loudness is the fault Preflight is expected to correct; the
    dynamics are what make the correction meaningful rather than cosmetic.
    """
    run(
        [
            "ffmpeg", "-y", "-hide_banner", "-loglevel", "error",
            "-f", "lavfi", "-i",
            f"testsrc2=size={WIDTH}x{HEIGHT}:rate={FRAME_RATE}:duration={DURATION}",
            "-f", "lavfi", "-i",
            f"sine=frequency=220:sample_rate=48000:duration={DURATION}",
            # A descending staircase rather than a loud/quiet switch. EBU R128
            # applies a relative gate that discards passages far below the
            # programme mean, so two extremes measure as almost no range at
            # all; a graded spread is what produces a real loudness range.
            "-filter_complex",
            "[1:a]volume='0.9*pow(0.5,floor(mod(t,24)/2.4))':eval=frame,"
            "aresample=48000[a]",
            "-map", "0:v", "-map", "[a]",
            "-c:v", "libx264", "-profile:v", "high", "-preset", "veryfast",
            "-b:v", VIDEO_BITRATE, "-minrate", VIDEO_BITRATE, "-maxrate", VIDEO_BITRATE,
            "-bufsize", "48M", "-pix_fmt", "yuv420p",
            "-aspect", "16:9",
            "-color_primaries", "bt709", "-color_trc", "bt709", "-colorspace", "bt709",
            # AC-3 is genuinely constant bitrate, so "from 320 kbit/s" is met
            # exactly rather than approximately.
            "-c:a", "ac3", "-b:a", "320k", "-ar", "48000", "-ac", "2",
            "-movflags", "+faststart",
            str(path),
        ],
        f"master.mov - {WIDTH}x{HEIGHT}p{FRAME_RATE}, {VIDEO_BITRATE}, AC-3 320k",
    )


def make_subtitles(path: Path) -> None:
    """WebVTT, where Artdocfest requires SubRip. A fault Preflight may fix."""
    path.write_text(
        "WEBVTT\n\n"
        "1\n00:00:00.000 --> 00:00:06.000\nA field, before anyone arrives.\n\n"
        "2\n00:00:06.000 --> 00:00:13.000\nThe sound builds, then falls away.\n\n"
        "3\n00:00:13.000 --> 00:00:20.000\nNothing here is louder than it should be.\n",
        encoding="utf-8",
        newline="\n",
    )
    print("  subtitles.vtt - WebVTT where SubRip is required")


def make_poster(path: Path) -> None:
    from PIL import Image, ImageDraw

    image = Image.new("RGB", (1920, 1080), (14, 16, 22))
    draw = ImageDraw.Draw(image)
    for y in range(0, 1080, 3):
        shade = int(18 + 40 * (y / 1080))
        draw.line([(0, y), (1920, y)], fill=(shade, shade + 4, shade + 12))
    draw.rectangle([120, 430, 1800, 650], fill=(10, 11, 16))
    draw.text((160, 520), "A QUIET FIELD", fill=(238, 238, 240))
    image.save(path, "JPEG", quality=94)
    print("  poster.jpg - 1920x1080")


def main() -> None:
    FIXTURE_DIR.mkdir(parents=True, exist_ok=True)
    print(f"generating deliverable fixture in {FIXTURE_DIR}")

    make_master(FIXTURE_DIR / "master.mov")
    make_subtitles(FIXTURE_DIR / "subtitles.vtt")
    make_poster(FIXTURE_DIR / "poster.jpg")

    print("\nbuilt to Artdocfest's published FullHD specification, with two")
    print("faults left for Preflight to correct:")
    print("  audio loudness    far above the published -18..-21 LUFS window")
    print("  subtitle format   WebVTT where SubRip is required")
    print("\nand nothing else wrong, because a finished master should not be.")


if __name__ == "__main__":
    main()
