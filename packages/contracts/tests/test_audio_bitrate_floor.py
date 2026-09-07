"""The delivered audio must actually measure at or above the published floor.

Artdocfest publishes "Audio Bitrate: from 320 kbit/s". Preflight built a
package whose audio measured 212 kbit/s and called it VERIFIED, because the
requirement had been set aside along with three genuinely misread siblings that
shared its field. Restoring the requirement is only half the fix: the repair
has to produce a file that satisfies it.

That turned out not to be a matter of asking for more. FFmpeg's native AAC
encoder treats ``-b:a`` as a hint and saturated near 139 kbit/s on this
material whether it was asked for 320k, 384k, 512k or 640k. So these tests
measure the encoded result rather than trusting the request, which is the only
form of this test worth having.

They run ffmpeg for real. A mocked encoder would have happily reported the
bitrate we asked for, which is precisely the bug.
"""

from __future__ import annotations

import json
import shutil
import subprocess
from pathlib import Path

import pytest
from preflight_contracts.repairs import DELIVERY_AUDIO_BITRATE_BPS, normalise_loudness

pytestmark = pytest.mark.skipif(
    shutil.which("ffmpeg") is None or shutil.which("ffprobe") is None,
    reason="ffmpeg and ffprobe are required to measure an encode honestly",
)

#: The floor Artdocfest publishes, in bits per second.
PUBLISHED_FLOOR_BPS = 320_000


def _measure_audio(path: Path) -> dict:
    proc = subprocess.run(
        [
            "ffprobe", "-v", "error", "-select_streams", "a",
            "-show_entries", "stream=codec_name,bit_rate,sample_rate,channels",
            "-of", "json", str(path),
        ],
        capture_output=True, text=True, check=True,
    )
    return json.loads(proc.stdout)["streams"][0]


def _picture_md5(path: Path) -> str:
    proc = subprocess.run(
        ["ffmpeg", "-v", "error", "-i", str(path), "-map", "0:v", "-f", "md5", "-"],
        capture_output=True, text=True, check=True,
    )
    return proc.stdout.strip()


@pytest.fixture(scope="module")
def quiet_master(tmp_path_factory) -> Path:
    """Sparse programme material, which is what defeated the AAC encoder.

    A low-level tone under a still frame: the encoder has little to describe,
    so it spends far fewer bits than requested. Busy material would hide the
    bug.
    """
    path = tmp_path_factory.mktemp("fixtures") / "quiet.mov"
    subprocess.run(
        [
            "ffmpeg", "-y", "-loglevel", "error",
            "-f", "lavfi", "-i", "color=c=black:s=320x240:r=25:d=6",
            "-f", "lavfi", "-i", "sine=frequency=220:sample_rate=48000:duration=6",
            "-c:v", "libx264", "-pix_fmt", "yuv420p",
            "-c:a", "ac3", "-b:a", "320k", "-ar", "48000",
            "-shortest", str(path),
        ],
        check=True, capture_output=True,
    )
    return path


class TestTheRepairMeetsThePublishedFloor:
    def test_the_configured_bitrate_clears_the_floor(self):
        """Headroom is deliberate: the floor is what must hold after encoding."""
        assert DELIVERY_AUDIO_BITRATE_BPS > PUBLISHED_FLOOR_BPS

    def test_normalised_audio_measures_at_or_above_the_floor(self, quiet_master, tmp_path):
        """The regression. The shipped package measured 212630 here."""
        out = tmp_path / "normalised.mov"
        normalise_loudness(quiet_master, out, target_lufs=-19.5, true_peak_dbtp=-3.0)

        measured = _measure_audio(out)
        assert int(measured["bit_rate"]) >= PUBLISHED_FLOOR_BPS, (
            f"delivered audio measured {measured['bit_rate']} bps, "
            f"below the published floor of {PUBLISHED_FLOOR_BPS}"
        )

    def test_the_encoder_delivers_what_it_was_asked_for(self, quiet_master, tmp_path):
        """A hint is not a guarantee. This encoder has to be held to the number."""
        out = tmp_path / "normalised.mov"
        normalise_loudness(quiet_master, out, target_lufs=-19.5, true_peak_dbtp=-3.0)
        assert int(_measure_audio(out)["bit_rate"]) == DELIVERY_AUDIO_BITRATE_BPS

    def test_the_codec_is_one_the_destinations_accept(self, quiet_master, tmp_path):
        """The published rule lists AAC and AC-3 together; AC-3 is in force."""
        out = tmp_path / "normalised.mov"
        normalise_loudness(quiet_master, out, target_lufs=-19.5, true_peak_dbtp=-3.0)
        assert _measure_audio(out)["codec_name"] in ("aac", "ac3")

    def test_the_sample_rate_survives(self, quiet_master, tmp_path):
        out = tmp_path / "normalised.mov"
        normalise_loudness(quiet_master, out, target_lufs=-19.5, true_peak_dbtp=-3.0)
        assert int(_measure_audio(out)["sample_rate"]) == 48_000

    def test_the_picture_is_still_untouched(self, quiet_master, tmp_path):
        """Raising the audio rate must not have cost the picture guarantee."""
        out = tmp_path / "normalised.mov"
        result = normalise_loudness(quiet_master, out, target_lufs=-19.5, true_peak_dbtp=-3.0)
        assert _picture_md5(quiet_master) == _picture_md5(out)
        assert result.parameters["mode"] == "linear"
