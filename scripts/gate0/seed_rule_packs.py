"""Hand-verified rule packs for the two Gate 0 destinations.

These were transcribed by a human from the official pages cited in
docs/destinations.md. They exist for one purpose: to be the **ground truth**
that the Gemini extraction is scored against.

Gate 0 passes only if agent-extracted rules match these closely enough to trust.
If extraction cannot reach that bar on two destinations whose specifications are
published as plain tables, it will not reach it on harder sources, and the
product does not work. That is the kill decision, and it happens here — before
any interface is built.

This file is not a fallback. Nothing in the running product may serve these
rules in place of a live retrieval; doing so would be exactly the fabricated
provider result the project forbids.
"""

from __future__ import annotations

import sys
from datetime import datetime, timezone
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[2] / "packages" / "contracts"))

from preflight_contracts.rules import (  # noqa: E402
    AssetType, Confidence, Operator, Rule, RulePack, Severity, SourceEvidence, TrustTier,
)

RETRIEVED_AT = "2026-08-09T00:00:00+00:00"


def _evidence(eid: str, url: str, excerpt: str) -> SourceEvidence:
    import hashlib
    return SourceEvidence(
        evidence_id=eid,
        url=url,
        retrieved_at=RETRIEVED_AT,
        source_hash=hashlib.sha256(excerpt.encode()).hexdigest()[:16],
        quoted_excerpt=excerpt,
        trust_tier=TrustTier.OFFICIAL,
    )


def _rule(
    rid: str, asset: AssetType, field_name: str, op: Operator, value,
    eid: str, severity: Severity = Severity.REQUIRED, note: str = "",
) -> Rule:
    return Rule(
        rule_id=rid, asset_type=asset, field_name=field_name, operator=op,
        value=value, severity=severity, source_evidence_id=eid,
        confidence=Confidence.HIGH, note=note,
    )


# ---------------------------------------------------------------------------
# YouTube — support.google.com/youtube/answer/1722171
# ---------------------------------------------------------------------------

YOUTUBE_URL = "https://support.google.com/youtube/answer/1722171"

_yt_ev = {
    "yt_container": _evidence(
        "yt_container", YOUTUBE_URL,
        "Container: MP4. No Edit Lists. moov atom at the front of the file (Fast Start).",
    ),
    "yt_video": _evidence(
        "yt_video", YOUTUBE_URL,
        "Video codec: H.264. Progressive scan. High Profile. 2 consecutive B frames. Closed GOP.",
    ),
    "yt_audio": _evidence(
        "yt_audio", YOUTUBE_URL,
        "Audio codec: AAC-LC. Channels: Stereo or Stereo + 5.1. Sample rate 48 kHz. "
        "Stereo audio bitrate: 384 kbps.",
    ),
    "yt_bitrate": _evidence(
        "yt_bitrate", YOUTUBE_URL,
        "Recommended video bitrates for SDR uploads, standard frame rate (24, 25, 30): 1080p — 8 Mbps.",
    ),
    "yt_colour": _evidence(
        "yt_colour", YOUTUBE_URL,
        "Recommended color space: BT.709. Standard aspect ratio: 16:9.",
    ),
}

YOUTUBE = RulePack(
    destination_id="youtube",
    version=1,
    evidence=_yt_ev,
    rules=[
        _rule("yt-1", AssetType.VIDEO, "container", Operator.EQ, "mp4", "yt_container"),
        _rule("yt-2", AssetType.VIDEO, "fastStart", Operator.EQ, True, "yt_container",
              note="moov atom must precede mdat so playback can begin before download completes"),
        _rule("yt-3", AssetType.VIDEO, "codec", Operator.EQ, "h264", "yt_video"),
        _rule("yt-4", AssetType.VIDEO, "scanType", Operator.EQ, "progressive", "yt_video"),
        _rule("yt-5", AssetType.VIDEO, "displayAspectRatio", Operator.EQ, "16:9", "yt_colour"),
        _rule("yt-6", AssetType.VIDEO, "colourPrimaries", Operator.EQ, "bt709", "yt_colour",
              severity=Severity.RECOMMENDED),
        _rule("yt-7", AssetType.VIDEO, "frameRate", Operator.IN, [24, 25, 30, 48, 50, 60], "yt_video"),
        _rule("yt-8", AssetType.VIDEO, "bitrateBps", Operator.EQ, 8_000_000, "yt_bitrate",
              severity=Severity.RECOMMENDED, note="1080p SDR at standard frame rate"),
        _rule("yt-9", AssetType.AUDIO, "codec", Operator.IN, ["aac", "opus"], "yt_audio"),
        _rule("yt-10", AssetType.AUDIO, "sampleRateHz", Operator.EQ, 48000, "yt_audio"),
        _rule("yt-11", AssetType.AUDIO, "channels", Operator.IN, [2, 6], "yt_audio"),
        _rule("yt-12", AssetType.AUDIO, "bitrateBps", Operator.GTE, 384_000, "yt_audio",
              severity=Severity.RECOMMENDED),
        # Deliberately absent: no loudness rule. YouTube publishes no delivery
        # loudness target on this page, so Preflight asserts none. See
        # docs/destinations.md — an unstated requirement is not an invitation
        # to import one from a blog.
    ],
)


# ---------------------------------------------------------------------------
# Artdocfest — artdocfest.com/en/content/technical-requirements/
# ---------------------------------------------------------------------------

ADF_URL = "https://artdocfest.com/en/content/technical-requirements/"

_adf_ev = {
    "adf_video": _evidence(
        "adf_video", ADF_URL,
        "Container: Mp4, MOV. Codec: H264. Frame rate: 25 fps / 24 fps / 23,976 fps / "
        "29,97 fps / 30 fps. FullHD: 1920x1080.",
    ),
    "adf_bitrate": _evidence(
        "adf_bitrate", ADF_URL,
        "Bitrate (constant): FHD/2K — from 20 to 30 Mbps.",
    ),
    "adf_audio": _evidence(
        "adf_audio", ADF_URL,
        "Audio: AAC, AC3. Bitrate from 320 kbit/s. Sample rate 48 kHz. "
        "Sound level: -10dB (RMS), -3 (Peak). Integrated loudness: -18... -21. "
        "Dynamic range 25 - 30dB.",
    ),
    "adf_subs": _evidence(
        "adf_subs", ADF_URL,
        "Subtitles: SubRip (.srt). Burned-in subtitles are not allowed.",
    ),
}

ARTDOCFEST = RulePack(
    destination_id="artdocfest",
    version=1,
    evidence=_adf_ev,
    rules=[
        _rule("adf-1", AssetType.VIDEO, "container", Operator.IN, ["mp4", "mov"], "adf_video"),
        _rule("adf-2", AssetType.VIDEO, "codec", Operator.EQ, "h264", "adf_video"),
        _rule("adf-3", AssetType.VIDEO, "frameRate", Operator.IN,
              [23.976, 24, 25, 29.97, 30], "adf_video"),
        _rule("adf-4", AssetType.VIDEO, "widthPx", Operator.EQ, 1920, "adf_video",
              note="FullHD delivery"),
        _rule("adf-5", AssetType.VIDEO, "heightPx", Operator.EQ, 1080, "adf_video"),
        _rule("adf-6", AssetType.VIDEO, "bitrateBps", Operator.BETWEEN,
              [20_000_000, 30_000_000], "adf_bitrate"),
        _rule("adf-7", AssetType.AUDIO, "codec", Operator.IN, ["aac", "ac3"], "adf_audio"),
        _rule("adf-8", AssetType.AUDIO, "sampleRateHz", Operator.EQ, 48000, "adf_audio"),
        _rule("adf-9", AssetType.AUDIO, "bitrateBps", Operator.GTE, 320_000, "adf_audio"),
        _rule("adf-10", AssetType.AUDIO, "integratedLoudnessLufs", Operator.BETWEEN,
              [-21.0, -18.0], "adf_audio",
              note="the requirement most often missed, and the one that is measurable"),
        _rule("adf-11", AssetType.AUDIO, "truePeakDbtp", Operator.LTE, -3.0, "adf_audio"),
        _rule("adf-12", AssetType.SUBTITLE, "format", Operator.EQ, "srt", "adf_subs"),
        _rule("adf-13", AssetType.SUBTITLE, "burnedIn", Operator.EQ, False, "adf_subs"),
    ],
)


GROUND_TRUTH: dict[str, RulePack] = {
    "youtube": YOUTUBE,
    "artdocfest": ARTDOCFEST,
}


def main() -> None:
    out = Path(__file__).resolve().parents[2] / "out" / "ground_truth"
    out.mkdir(parents=True, exist_ok=True)
    for name, pack in GROUND_TRUTH.items():
        (out / f"{name}.json").write_text(pack.to_json(), encoding="utf-8")
        required = len(pack.required_rules())
        print(f"{name:12} v{pack.version}  digest={pack.digest()}  "
              f"{len(pack.rules)} rules ({required} required)")
    print(f"\nwritten to {out}")


if __name__ == "__main__":
    main()
