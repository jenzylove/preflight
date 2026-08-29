# Preflight Design Direction

## Product

Preflight is a delivery readiness product for filmmakers.

It lives between:

**The film is finished**

and

**The film is ready to leave.**

A filmmaker gives Preflight a finished master and its destinations.

Preflight retrieves the destinations' current delivery requirements, measures the real media, exposes mismatches and conflicts, proposes safe repairs, refuses unsafe automatic work, independently verifies resulting packages, and creates evidence-backed delivery artifacts.

The product is already functional.

This design pass is not an opportunity to reinvent the product or replace working functionality.

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

# Primary motion reference

Use the supplied motion video as the PRIMARY reference for art direction and choreography.

Do not copy its branding, text, subject matter, flower/object, layout literally, or visual assets.

Study:

the amount of negative space

the scale of the primary visual

how elements occupy depth

the slow continuous motion

how scroll changes the composition

how objects overlap

how typography participates in the composition

the easing and pacing

how little conventional card UI is visible

how the page feels designed as one scene rather than assembled from sections

Translate those principles into Preflight.

Do not combine multiple unrelated visual styles.

---

# Landing hero

This is the most important visual moment in the product.

Do not begin with a dashboard screenshot.

Do not begin with a conventional centered SaaS heading and product card.

The hero should feel spatial and cinematic.

## Scene

Start with a finished film represented as one beautiful cinematic frame suspended in a dark environment.

The film frame is the central sculptural object of the hero.

It should feel almost physical.

Use subtle depth.

Allow restrained pointer movement on desktop if it improves the composition.

## Scroll choreography

As the user begins scrolling, the finished film separates into an exploded technical view.

The layers represent:

Picture

Audio waveform

Subtitle track

Metadata

Destination specification

These must remain part of ONE visual composition.

Do not turn them into five floating dashboard cards.

They should separate in depth and position as though Preflight is opening the finished film and inspecting everything inside it.

Small technical labels may accompany the layers.

Examples:

PICTURE

AUDIO · -19.4 LUFS

SUBTITLES · SRT

METADATA

DESTINATION SPEC

The exact displayed illustrative values may be adjusted for composition, but authenticated product measurements must always come from real data.

## Inspection moment

Destination requirements begin visually aligning against the appropriate film layers.

Show a restrained combination of:

verified property

warning

requirement mismatch

destination conflict

Do not flood the hero with statuses.

The animation is communicating what Preflight does, not reproducing the entire compatibility matrix.

## Resolution

After inspection, the layers should resolve back toward a coherent object.

The result should visually become a prepared destination package.

The final state should communicate:

VERIFIED

or an equivalent product state.

Then land the primary copy:

# Your film is finished.

# Make sure it's ready to leave.

Primary CTA:

**Prepare your film**

Secondary:

**Sign in**

The product name PRE­FLIGHT should have strong presence but should not compete with the main statement.

---

# Hero movement

Motion should feel:

slow

deliberate

smooth

expensive

spatial

restrained

Never frantic.

Never bouncy.

Never playful.

Never like a template animation.

Use GSAP / ScrollTrigger where appropriate.

Use CSS 3D transforms where enough.

Only introduce Three.js or React Three Fiber if genuine three-dimensional rendering materially improves the composition.

Do not add heavy technology merely because it sounds advanced.

The hero must remain performant.

Reduced motion users should receive a strong static or lightly animated version of the same composition.

---

# Landing page after hero

The hero is the spectacle.

The rest of the landing page should become increasingly restrained.

Do not try to make every section another Awwwards experiment.

The supporting story should cover:

## One finished master. Different destinations.

Visualize one film branching toward destination-specific requirements.

## Requirements change.

Show that Preflight retrieves current specifications and keeps their source evidence.

## Measure, never guess.

Show film properties and technical measurement elegantly.

## Safe repairs stay safe.

Explain the existing Green / Yellow / blocked model without making the UI childish.

## Verify the result.

Communicate that worker completion is not trusted automatically.

The result is independently remeasured.

## Every delivery keeps its evidence.

Introduce:

packages

passport

provenance

sources

hashes

delivery room

Finish with the primary CTA again.

---

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
