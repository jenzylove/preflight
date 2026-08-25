# Demo runbook

Everything below runs against real files, real published requirements and real
provider calls. There is no seeded state and no recorded response. If a step
fails, it failed — that is the point of writing it down this way.

## Before recording

```bash
python scripts/gate0/make_fixture.py     # synthesise the malformed master
python -m pytest -q                       # 141 tests
```

Confirm `ffmpeg` and `ffprobe` are on PATH, and that `.env` carries
`PARALLEL_API_KEY`, `GOOGLE_CLOUD_PROJECT` and `GOOGLE_APPLICATION_CREDENTIALS`.

## The 90 seconds

### 1. The problem, stated once (0:00–0:10)

> A finished film goes to several places. Each one publishes different
> technical requirements, those requirements change, and around a quarter of
> first submissions fail technical QC. Usually for something a machine could
> have measured.

### 2. Retrieval, live (0:10–0:30)

```bash
python scripts/gate3/run_extraction.py
```

On screen, in order:

- **Eight sources retrieved, two official.** The tier column is visible.
  Six are withheld as unverified — including, on a real run, a marketing blog
  and a Wikipedia page.
- **"extracting from 2 trusted sources (6 withheld as unverified)"**
- **Rules demoted by tier.** For Artdocfest: 126 rules extracted, 66 mandatory,
  60 demoted to context because of where they came from.
- **A live ambiguity.** Artdocfest publishes its requirements in English and in
  Russian, and the two pages state different video bitrates. Preflight marks
  the requirement AMBIGUOUS and shows both URLs. Nobody constructed this case.

Say plainly: *the model reads; it does not decide what to trust.*

### 3. The conflict (0:30–0:45)

```bash
python scripts/gate0/check_conflicts.py
```

```
[HARD] subtitle.burnedIn
  berlinale    required  eq True
    |- berlinale.de/...  "All ProRes subtitles must be burned-in.
                          Subtitles delivered as a separate file will not be accepted."
  artdocfest   required  eq False
    |- artdocfest.com/... "Subtitles: SubRip (.srt). Burned-in subtitles are not allowed."
```

> Two real festivals. Directly contradictory. Preflight quotes each one's own
> words and builds a separate version for each, rather than guessing which
> matters more.

### 4. Measure, repair, re-measure (0:45–1:15)

```bash
python scripts/gate0/run_spike.py
```

Point at four things:

| On screen | Why it matters |
|---|---|
| `integrated loudness -4.85 LUFS` against a published `-18..-21` window | The single most common rejection cause, measured not guessed |
| `REVIEW video.codec` — ProRes required, H.264 supplied | Preflight refuses to re-encode the picture silently |
| `original sha256 unchanged  True` | The master is untouched |
| `repaired picture identical to original  True` — same MD5 before and after | The metadata repair provably did not touch the image |

Then the decision block, including the line that says Berlinale is **not**
ready. Do not skip it:

> Artdocfest is ready. Berlinale is not, because it needs a ProRes master and
> burned-in subtitles, and neither is something Preflight will do to your film
> without asking. It tells you, and stops.

### 5. The receipt (1:15–1:30)

Open the passport. Show original hashes, each transformation, the rule pack
version, the cited sources with retrieval dates, and the limitations block —
which always ends with:

> Preflight verifies this package against the destination requirements
> published at the retrieval dates recorded below. It is not a guarantee that
> the destination will accept this delivery.

## What must be visible on screen

- Official source URLs, with retrieval dates
- Measured input properties, from ffprobe and ffmpeg
- The original asset hash, unchanged
- The decoded picture hash, identical before and after repair
- Validator results measured from the built package
- At least one thing Preflight refused to do, and why
- The deployed URL

## What not to claim

- Never "compliant". Say "meets published requirements as of *date*".
- Never that a destination will accept the delivery.
- Never that Preflight fixed something it only detected.

## If something fails live

Say what failed and move on. The project's entire argument is that it reports
what is true rather than what is convenient; a live failure handled honestly
costs less than a rehearsed result that hides one.
