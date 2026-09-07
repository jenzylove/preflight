# Preflight design

A record of the design as it shipped, not a brief for one still to be made.
Where it states a rule, that rule holds in the deployed product and there is
usually a check that says so.

## Product

Preflight is a delivery readiness product for filmmakers.

It lives between:

**The film is finished**

and

**The film is ready to leave.**

A filmmaker gives Preflight a finished master and its destinations.

Preflight retrieves the destinations' current delivery requirements, measures the real media, exposes mismatches and conflicts, proposes safe repairs, refuses unsafe automatic work, independently verifies resulting packages, and creates evidence-backed delivery artifacts.

Every screen described here is connected to that live backend. No screen in the
authenticated product renders invented data, and a new account genuinely starts
empty rather than seeded with a sample film.

---

# Core visual idea

Preflight should feel like a premium piece of film technology.

Not Netflix.

Not CapCut.

Not an editing suite.

Not Web3.

Not an AI SaaS dashboard.

Not a generic startup landing page.

The visual world should combine:

cinema

editorial design

post production

technical precision

quiet confidence

spatial motion

strong typography

large visual compositions

The public experience may be immersive.

The actual product workspace should become calmer and more precise.

---

# Landing page, as shipped

The public page is one editorial composition in a dusty mauve palette, not a
scene the reader has to drive. It was an animated exploded-film sequence
earlier in the build - a finished frame that came apart into picture, audio,
subtitles, metadata and a destination specification across roughly five
viewport heights. That is gone, deliberately, and should not come back. It
asked the reader to scroll a long way before the page said anything, and the
argument it made in motion is made faster in words and pictures.

## Hero

Palette `#b7a9b5`, with a soft radial wash toward the upper left. Everything
is set in the dark plum `#382d37`.

Left column, in reading order:

- the wordmark, small, `PRE—FLIGHT`, uppercase with wide tracking
- the headline, in the display serif at `clamp(4.6rem, 8.2vw, 8.8rem)`, set on
  three lines: *Ready before / it leaves / your hands.*
- one paragraph of plain description
- the primary call to action, **Prepare your film**, going to `/projects`

Right column, desktop only: two photographic images in soft organic crops -
a projector lens above right, a cinema auditorium below it, overlapping
slightly. Below the `lg` breakpoint the projector is dropped and the
auditorium image moves under the copy, because two overlapping crops in a
narrow column read as clutter rather than composition.

**Sign in** sits top right, quiet.

## Hero motion

A single parallax: the two images drift upward as the page scrolls, capped at
30px and 16px respectively over the first viewport height. It is driven by one
passive scroll listener writing two CSS custom properties on animation frames.
No animation library, no pinning, no scroll timeline.

It is deliberately almost imperceptible. It exists so the images sit in the
page rather than on it. Under `prefers-reduced-motion` both offsets are set to
zero and nothing else changes, because there is nothing else to change.

## The rule the hero must keep

The images never overlap the headline, the paragraph or the call to action.
This is checkable rather than a matter of taste: at the centre of the headline
and the centre of the CTA, the topmost painted element must be that element
itself. `scripts/shoot.mjs` asserts exactly that at 1440, 1280 and 390, and
also that the document never scrolls horizontally.

## Below the hero

Four sections, alternating between `#c9bec4` and `#b7a9b5`, closing on the
dark plum `#4a3948`. They get progressively quieter; the hero is the only
place that raises its voice.

1. **From finished master to confident delivery** - three numbered steps,
   separated by hairlines.
2. **Every part of the film that has to arrive intact** - a finishing-suite
   photograph beside a ruled list of what gets measured.
3. **One master. Different ways out** - the Berlinale and Artdocfest
   requirements as two columns divided by a real vertical rule. They were one
   filled panel with a one-pixel seam and read as a single block, which said
   the opposite of the heading above them.
4. **Know before you deliver** - the closing statement and the call to action
   again, on plum.

Separation across the page is done with hairlines and typography rather than
filled cards, which is why section three had to change to match.

## What the marketing page may and may not assert

The four checks listed in section two - picture, sound, subtitles, metadata -
are categories, not measurements. No number on the public page is presented as
having been measured from anyone's film. Every measurement shown inside the
authenticated product comes from the worker having opened the actual file.

# Public versus authenticated experience

There are two intentionally different modes.

## Public Preflight

Cinematic.

Immersive.

Editorial.

Spatial.

Emotionally connected to film.

## Preflight Workspace

Professional.

Quiet.

Precise.

Technical.

Easy to scan.

The transition from marketing to application should feel like entering the instrument behind the cinematic introduction.

---

# Authentication

Authentication is part of the real product.

Use the existing Identity Platform / Firebase implementation.

Do not rebuild authentication.

Create polished sign up and sign in experiences consistent with the design system.

---

# First-time workspace

Never populate fake projects.

For a new user, use an intentional empty state.

Suggested hierarchy:

**Your first delivery starts with a finished film.**

Upload your master and tell Preflight where it is going.

Primary action:

**Upload your master**

Show the real workflow subtly:

Master → Destinations → Preflight → Repair → Verify → Deliver

---

# Returning workspace

For a returning user:

**Good morning, [name].**

**Prepare your finished films for delivery.**

Primary action:

**New delivery**

Show actual projects.

Project cards should feel like film projects rather than SaaS database records.

Where real project imagery becomes available, use it.

Until that capability exists, use strong typography, project title, destination, and status rather than fake artwork.

Possible project states:

Needs attention

Inspection running

Repair approval required

Processing

Verified

Delivery active

Do not fabricate progress percentages.

---

# Project experience

The project should have a coherent sequence:

Master

Destinations

Preflight

Repair

Verification

Packages

Passport

Delivery

Do not expose backend architecture as navigation.

The user should think in terms of preparing a film, not managing database entities.

---

# Compatibility matrix

This remains one of the core product screens.

Preserve the product principle:

**Published requirement beside measured reality.**

Each important finding should clearly expose:

requirement

measured value

result

source

retrieval date

explanation

Conflicts appear above normal findings.

Use real deduplicated conflict output.

Do not reintroduce raw extraction noise.

---

# Rule review

Rule disposition must have a proper UI.

The user should be able to inspect:

the extracted requirement

the original source excerpt

source URL

retrieval time

Preflight's interpretation

why the rule currently affects readiness

Then use the existing backend disposition mechanism.

Setting a rule aside should feel like a review decision, not dismissing an annoying warning.

---

# Repair

Green operations:

Preflight may execute after explicit approval.

Yellow operations:

visible but cannot execute automatically.

Blocked operations:

Preflight refuses.

For every operation show:

what changes

why

which requirement caused it

what remains untouched

safety level

Avoid giant warning banners unless genuinely necessary.

---

# Verification

Make independent revalidation visually meaningful.

The user should understand:

the worker produced a result

Preflight does not trust that result automatically

the output is measured again

only then can a package become verified

A successful verification may have a restrained visual payoff.

No confetti.

---

# Passport

The Passport should be one of the most polished product screens.

It is an artifact, not a log dump.

Hierarchy should surface:

film identity

destination

verification state

original asset

transformations

source requirements

retrieval dates

validation

package identity

limitations

provenance

Technical detail must remain accessible without dominating the first view.

---

# Delivery room

The public delivery page should be elegant and extremely simple.

It is for the recipient, not the filmmaker operating Preflight.

Only expose data approved by the backend public response.

Never expose private project information or storage details.

---

# Visual system

Preferred:

near-black / charcoal

high-quality off-white

subtle neutral surfaces

restrained borders

strong editorial typography

cinematic image treatment

one restrained accent

semantic status colors

large negative space

precise spacing

Avoid:

purple-blue SaaS gradients

glass cards everywhere

excessive rounded rectangles

random blobs

sparkles

AI iconography

Web3 design language

giant dashboard grids

every section inside a card

generic Tailwind aesthetics

fake graphs

decorative metrics

---

# Typography

Typography is a primary visual element.

Use a strong editorial / grotesk pairing suitable for film and professional software.

Headlines can be large and cinematic.

Product text must remain highly readable.

Monospace is reserved for genuinely technical values:

hashes

codecs

digests

rule ids

measurement values where useful

Do not make the application entirely monospace.

---

# Motion inside the application

Keep application motion subtle.

Suitable:

route transitions

evidence expansion

processing state

verification changes

project transitions

status changes

Not suitable:

floating decorative objects behind decision screens

parallax behind data tables

constant ambient movement

anything that makes technical comparison harder to read

---

# Mobile

Desktop may receive the full cinematic composition.

Mobile does not need to reproduce every depth effect.

Simplify intelligently.

Preserve:

the film visual

the concept of separation

the core headline

the CTA

the emotional quality

The application itself must remain fully usable on mobile.

---

# Quality bar

Do not evaluate the frontend by whether components technically exist.

The design must be visually inspected in a real browser.

A page is not finished because:

it compiles

the CSS exists

the DOM contains the expected element

the animation code exists

The page is finished only after it has been rendered and visually inspected.

Specifically inspect:

composition

spacing

typography

motion

image scale

depth

alignment

responsive behavior

visual hierarchy

whether the result actually resembles the art-direction goal

If browser access is unavailable, report that visual verification is blocked.

Do not report visual PASS based on source inspection alone.

---

# Non-negotiable product constraints

Preserve the existing backend.

Preserve real authentication.

Preserve real uploads.

Preserve real measurements.

Preserve current requirement retrieval.

Preserve compatibility logic.

Preserve dispositions.

Preserve repair safety.

Preserve independent validation.

Preserve packages.

Preserve passport.

Preserve delivery room.

Do not replace working flows with mocks while redesigning them.

No fake sample projects.

No fake verification.

No fake measurements.

No fake requirements.

No fake processing progress.

---

# Implementation philosophy

Design first.

Implement.

Render.

Inspect.

Adjust.

Render again.

Do not implement the entire frontend before checking whether the core art direction works.

The first visual milestone is the public landing hero.

The design language for the rest of the product should only proceed after that hero has been rendered and visually approved.
