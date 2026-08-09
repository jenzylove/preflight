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

**Gate 0 complete.** The central transaction is proven end to end with scripts
only, against two real destinations and one deliberately malformed fixture. No
interface has been built yet — that was the point.

```
9 mismatches detected against real published rules
4 repaired by deterministic operations
original asset sha256 unchanged
decoded picture bit-identical before and after metadata repair
1 irreconcilable cross-destination conflict found and cited
```

Reproduce it:

```bash
python scripts/gate0/make_fixture.py     # synthesise the malformed master
python scripts/gate0/run_spike.py        # measure, compare, repair, re-measure
python scripts/gate0/check_conflicts.py  # prove the destinations really conflict
cd packages/contracts && python -m pytest tests -q
```

Requires `ffmpeg` and `ffprobe` on PATH, plus `pillow` and `pytest`.

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

- **YouTube** — `support.google.com/youtube/answer/1722171`
- **Artdocfest** — `artdocfest.com/en/content/technical-requirements/`

Netflix was evaluated and rejected: its delivery specifications require partner
login, and the publicly reachable QC page states no numeric values. That is a
real constraint on the product, not a demo inconvenience, and it is why
user-supplied private specifications are a first-class path rather than a
fallback. See [docs/destinations.md](docs/destinations.md).

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
