# Demo runbook

Everything below runs against the deployed system with real provider calls.
There is no seeded state, no recorded response and no demo account with a
sample film in it. If a step fails, it failed — which is the point of writing
it down this way.

- Frontend: <https://preflight-web-584136898465.us-central1.run.app>
- API: <https://preflight-api-584136898465.us-central1.run.app>

## Before recording

```bash
python scripts/gate0/make_fixture.py              # the deliberately broken master
python scripts/gate0/make_deliverable_fixture.py  # the one built to be delivered
python -m pytest -q                                # 193 tests
```

Then, in a browser:

1. Sign up a fresh account. It will be empty, which is what you want on
   camera — the empty state is part of the argument.
2. Create the project and **upload the master ahead of time**. The deliverable
   fixture is 72 MB and the upload plus server-side measurement is the slowest
   thing in the product. Do not spend demo time watching a progress bar.
3. Run preflight once so the requirements are retrieved and cached, then stop.
   Leave the repair plan unapproved — approving it live is the good moment.

Have a second tab open on the landing page.

## The 90 seconds

### 1. The problem, stated once (0:00–0:10)

Open the landing page.

> A finished film goes to several places. Each publishes different technical
> requirements, those requirements change, and around a quarter of first
> submissions fail technical QC — usually for something a machine could have
> measured.

Scroll once to *One master. Different ways out.* Do not narrate the page.

### 2. What the film actually is (0:10–0:30)

Go to the project's **Master** step.

Point at the measured properties and say where they came from:

> Nothing here was typed in or guessed. Preflight opened the file on the
> server and measured it, and the tool and version that did it are recorded
> next to the numbers.

Expand **Provenance**. Show the SHA-256 and that the original is immutable.

### 3. Published beside measured (0:30–0:50)

Go to **Preflight**.

The screen to linger on. Two things to point at:

| On screen | Say |
|---|---|
| A failing row, published value beside measured value | "The requirement, and what the file actually is. Never collapsed into a score." |
| **Where this comes from** on that row | "Every requirement is quoted from the destination's own page, with the date it was retrieved." |

If both destinations are selected, the conflict card sits above everything:

> The Berlinale requires burned-in subtitles. Artdocfest forbids them and
> wants a SubRip file. No single delivery satisfies both, so Preflight builds
> two — and quotes each festival's own sentence for why.

### 4. What it will and will not do (0:50–1:10)

Go to **Repair**.

> Green is what Preflight will do: deterministic, and it never writes to your
> original. Yellow it shows you and refuses to run, because re-encoding the
> picture changes the film and that is not a decision a tool should make
> quietly.

Approve the green plan on camera. Then, while it runs:

> The worker reports success when it finishes. Preflight does not take its
> word for it.

### 5. The recheck, and the receipt (1:10–1:30)

Go to **Packages** when the job completes.

Point at the transformations, and specifically at *picture bit-identical to
your original* on the metadata repair.

Then open the **Passport**: original hashes, what changed, whose requirements
it was measured against and when they were retrieved, and the limitations —
which always end with the line that Preflight verifies against published
requirements and does not guarantee acceptance.

Create a delivery room and open the link in a private window. Show that the
recipient sees the package hash and the limitations, and nothing about the
project, the owner or where the files are stored.

## The parts worth showing that are easy to skip

- **The empty state.** No sample project. It is evidence, not a gap.
- **The destination Preflight cannot read.** On the Destinations step,
  YouTube and Netflix are listed as unavailable with the reason. A product
  that says what it cannot do is making a claim about the rest.
- **A requirement set aside.** On a rule that was misextracted, open
  **Review this requirement**: the source excerpt, the URL, and the mandatory
  reason that ends up printed on the passport.
- **Berlinale staying unverified.** That is the product working. Say so.

## What must be visible on screen

- Official source URLs, with retrieval dates
- Measured input properties, and the tool that measured them
- The original asset hash, unchanged
- The decoded picture hash, identical before and after repair
- Validator results measured from the built package
- At least one thing Preflight refused to do, and why
- The deployed URL

## What not to claim

- Never "compliant". Say "meets published requirements as of *date*".
- Never that a destination will accept the delivery.
- Never that Preflight fixed something it only detected.
- Never that a number on the landing page was measured from a real film. The
  four checks listed there are categories, not measurements.

## If something fails live

Say what failed and move on. The project's entire argument is that it reports
what is true rather than what is convenient; a live failure handled honestly
costs less than a rehearsed result that hides one.

## Evidence, if a judge asks for it

The scripts are the receipts behind the interface, and they run on their own:

```bash
python scripts/gate0/run_spike.py        # measure, compare, repair, re-measure
python scripts/gate0/check_conflicts.py  # the destinations really do conflict
python scripts/gate3/run_extraction.py   # live retrieval and extraction, scored
python scripts/e2e_verified.py           # the whole path, against the deployment
```

`scripts/shoot.mjs` captures the landing page at desktop and mobile widths and
asserts that nothing overlaps the headline or the call to action. It drives the
system Chrome and needs `playwright-core` installed in `apps/web`.
