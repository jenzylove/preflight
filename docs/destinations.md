# Gate 0 destination selection

Two destinations were required for the Gate 0 spike. Selection criteria:

1. Requirements published **publicly, without authentication** (a retrieval agent must be able to reach them).
2. Requirements stated as **concrete, checkable values**, not prose deferrals.
3. The two destinations must **genuinely conflict** on at least one requirement, so the "one master cannot satisfy every destination" thesis is demonstrable rather than asserted.

## Rejected: Netflix

Netflix's *Post Production Branded Delivery Specifications* and *Technical QC and Checks for Branded IMP Delivery* live in the Netflix Partner Help Center and **require login**. The publicly reachable QC article states no numeric targets — it defers every value ("frame rate", "resolution", "color space", "color range") to the authenticated specification document.

This is a real product constraint, not a demo inconvenience: the highest-value destinations publish their specs behind partner portals. Preflight's answer is the **private specification upload** path (FR-5) — the user supplies the PDF they already have access to, it is marked private, and it is never sent to the retrieval provider. Netflix is therefore a *private-spec* destination in the product, not a *retrieved-spec* destination.

## Destination A — YouTube

Source: <https://support.google.com/youtube/answer/1722171> (public, no login)

| Field | Requirement |
|---|---|
| Container | MP4, `moov` atom at front (Fast Start), no edit lists |
| Video codec | H.264, High Profile, progressive, 2 B-frames, closed GOP |
| Audio codec | AAC-LC, Opus, or Eclipsa Audio |
| Sample rate | 48 kHz |
| Channels | Stereo, or Stereo + 5.1 |
| Audio bitrate | Stereo 384 kbps; mono 128 kbps; 5.1 512 kbps |
| Video bitrate (1080p SDR, 24–30 fps) | 8 Mbps |
| Frame rate | Encode at the recorded frame rate; 24, 25, 30, 48, 50, 60 |
| Aspect ratio | 16:9 |
| Colour | BT.709 |

Loudness is **not specified on this page**. YouTube applies playback normalization rather than publishing a delivery target. Under the source-tier rules this means Preflight must emit **no loudness rule** for YouTube — an absence is not a licence to invent one. Any loudness figure for YouTube found on a blog or forum is Tier D and cannot become a mandatory rule.

## Destination B — Artdocfest

Source: <https://artdocfest.com/en/content/technical-requirements/> (public, no login)

| Field | Requirement |
|---|---|
| Container | MP4 or MOV |
| Video codec | H.264 |
| Frame rate | 23.976, 24, 25, 29.97, or 30 fps |
| Resolution (FullHD) | 1920×1080 |
| Video bitrate (FHD/2K) | 20–30 Mbps, constant |
| Audio codec | AAC or AC-3 |
| Audio bitrate | ≥ 320 kbps |
| Sample rate | 48 kHz |
| Integrated loudness | −18 to −21 LUFS |
| Peak | −3 dB |
| Dynamic range | 25–30 dB |
| Subtitles | SubRip `.srt`; **burned-in subtitles are not allowed** |

## The conflict this pair produces

| Field | YouTube | Artdocfest | Consequence |
|---|---|---|---|
| Video bitrate @ 1080p | 8 Mbps | 20–30 Mbps | **Direct conflict.** No single encode satisfies both. Two derived video assets are required — and Preflight can prove *why*, with citations, instead of the user guessing. |
| Integrated loudness | not specified | −18 to −21 LUFS | Preflight measures the master, reports the Artdocfest result, and stays silent for YouTube. Demonstrates that an unstated requirement produces no rule. |
| Subtitle format | WebVTT accepted | SRT only, no burn-in | Format conversion is required in one direction only. |

The bitrate conflict is the demo's strongest single moment: it is the case where the honest answer is *"you need two masters, and here is the published sentence from each destination that says so."*

## Trust tiers applied

| Source | Tier | Can create a mandatory rule? |
|---|---|---|
| `support.google.com/youtube/answer/1722171` | A — official destination documentation | Yes |
| `artdocfest.com/en/content/technical-requirements/` | A — official destination documentation | Yes |
| Netflix Partner Help Center (authenticated) | B — private specification, user-supplied | Yes, after user confirmation |
| Blog posts, forums, aggregator "spec guides" | D | No — retained as unverified context only |
