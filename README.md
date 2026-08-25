# Preflight

**Never get rejected for something a machine could have measured.**

Preflight sits between "the film is finished" and "the film is delivered". It
retrieves what each destination *currently* requires, measures what your file
actually is, repairs the gaps it can repair safely, independently re-measures
the result, and hands you a verified package with a receipt.

Around 20–30% of first submissions to major platforms fail technical QC. The
most common causes — loudness outside the published window, a missing or wrong
aspect-ratio flag — are all things a tool can measure in seconds. Preflight
measures them before someone else does, three weeks later, in a rejection email.

Built for the [Agentic Cinema](https://agentic-cinema.devpost.com/) hackathon,
Parallel track.

---

## Status

Gates 0 through 6 complete: the transaction is proven, the schema and state
machines enforce the safety properties, retrieval and extraction run live
against real destinations, and the worker, validator, passports and delivery
rooms are built and tested.

Measured, not asserted:

```
mean extraction recall vs. human transcription   96%
requirement mismatches found on a real fixture    9
repaired by deterministic operations              4
original asset sha256                             unchanged
decoded picture through metadata repair           bit-identical
cross-destination conflicts found and cited       1 (hard)
tests                                           141
```

Reproduce it:

```bash
python scripts/gate0/make_fixture.py     # synthesise the malformed master
python scripts/gate0/run_spike.py        # measure, compare, repair, re-measure
python scripts/gate0/check_conflicts.py  # prove the destinations really conflict
python scripts/gate3/run_extraction.py   # live retrieval + extraction, scored
python -m pytest -q
```

The first three need `ffmpeg` and `ffprobe` on PATH. The fourth needs
`PARALLEL_API_KEY` and a Google Cloud project in `.env` — see `.env.example`.

---

## How it works

```
current cited requirements
  → measured asset properties
  → explicit repair plan
  → your approval
  → independent revalidation
  → destination package
  → evidence receipt
```

Five commitments hold the whole thing up:

**Measure, never guess.** A model may read a requirement; only a tool may state
a fact about a file. Every number Preflight asserts comes from ffprobe, ffmpeg's
EBU R128 implementation, or Pillow, with the tool version recorded alongside it.

**Cite every requirement.** A rule without an accessible source, a quoted
excerpt, a retrieval timestamp and a source hash cannot exist. Severity is
derived from the source's trust tier *in Python, after the model returns* — so
no model output can promote a forum post into a mandatory requirement.

**Preserve the original.** The approved master is immutable. Repairs write new
files, and the metadata repair proves it left the image alone by comparing the
decoded video stream's hash before and after.

**Separate ready from accepted.** Preflight verifies against published rules. It
does not, and cannot, guarantee that a third party will accept your film. Every
passport carries its retrieval date and its unresolved limitations.

**Fail closed.** Contradictory sources, low-confidence extraction, or an
unmeasured property block readiness rather than passing quietly.

---

## Repair safety

| Level | Meaning | Behaviour |
|---|---|---|
| **Green** | Deterministic, non-creative, provably non-destructive | Runs after explicit approval of a digest-bound plan |
| **Yellow** | Can alter quality, timing, framing or meaning | Reported and explained; never automatic |
| **Red** | Requires professional mastering or authority Preflight does not have | Blocked, with the reason stated |

Green operations: EBU R128 two-pass loudness normalisation (linear mode, so the
mix is moved rather than reshaped), container and display-metadata rewrite with
`-c copy`, subtitle format conversion, poster pad-fit, metadata normalisation,
SHA-256 manifests.

Re-encoding the picture is yellow — always. When Artdocfest mandates 20–30 Mbps
and your master is 8 Mbps, Preflight tells you, cites the sentence, and stops.
Deciding to re-encode someone's film is not a decision a tool should make
quietly.

---

## Destinations

Gate 0 uses two destinations whose requirements are published publicly, in
concrete values, and which genuinely conflict:

- **Berlinale** — `berlinale.de/en/film-entry/technical-specifications/festival-media.html`
- **Artdocfest** — `artdocfest.com/en/content/technical-requirements/`

They conflict in a way that cannot be reconciled: the Berlinale mandates
burned-in subtitles and explicitly rejects sidecar files, while Artdocfest
mandates SubRip and forbids burned-in subtitles. Preflight quotes each
destination's own sentence and builds a separate version for each.

Two destinations were evaluated and rejected, for reasons that shape the
product rather than the demo:

- **Netflix** publishes its delivery specifications behind partner login.
- **YouTube** publishes its encoding specification through script. The page is
  public and authoritative, but extracting it returns 4 KB of prose containing
  no bitrate, frame rate or aspect ratio at all.

A destination whose requirements cannot be read is a real limit. Preflight
scores the machine-readability of what it retrieves and says so, and the answer
for those destinations is the private-specification path: the user supplies the
document they already have, it is marked private, and it never reaches a
retrieval provider. See [docs/destinations.md](docs/destinations.md).

---

## Architecture

```
Browser ── Next.js UI
              │
              ├── Firebase Authentication
              ├── local metadata preflight
              └── resumable upload to private Cloud Storage
                      │
FastAPI on Cloud Run ─┤
              ├── PostgreSQL          project, rule-pack and package lineage
              ├── compatibility engine  deterministic, no model involved
              ├── repair planner        dependency graph + plan digest
              └── Cloud Tasks ── isolated media worker on Cloud Run

Gemini Enterprise Agent Platform (Vertex AI Agent Engine + ADK)
              ├── Parallel search tool   destination requirement retrieval
              ├── requirement extraction into a strict closed schema
              └── ambiguity and conflict analysis
```

Boundaries that are enforced, not merely intended: Parallel never receives
private media or private specifications; the agent can never mark a package
verified; workers cannot reach unrelated projects; delivery links never expose
bucket paths.

---

## Repository

```
packages/contracts/     rule schema, compatibility engine, inspection, repairs
packages/fixtures/      synthesised malformed demo media (no third-party footage)
scripts/gate0/          the kill-spike: seed packs, fixture, end-to-end run
docs/                   destination selection, trust model, runbook
```

---

## Licence

Apache 2.0. See [LICENSE](LICENSE).
