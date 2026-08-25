# Rule source policy

Preflight asserts requirements about other people's films. A requirement it
gets wrong sends a producer to re-master something that was already correct, or
worse, tells them a delivery is ready when it will be rejected. This policy is
what stops that.

## The one rule

**A model may read a requirement. Only a source may create one.**

Gemini proposes structured rules from retrieved text. It cannot decide how much
those rules are trusted. Trust is assigned in Python, from the URL the text came
from, after the model returns.

## Tiers

| Tier | Source | May create a mandatory rule? |
|---|---|---|
| A | The destination's own published documentation | Yes |
| B | A specification the user uploaded and confirmed | Yes |
| C | A standard the destination explicitly references | Only for the clauses it cites |
| D | Blog, forum, aggregator, search snippet | **Never** |

Tier is decided by `classify_tier()` comparing the URL's host against the
destination's known official domains. A subdomain of an official domain is
Tier A. `youtube.com.evil.example` is Tier D, and so is `notyoutube.com`.

## What this prevents, concretely

The first live Parallel query for YouTube's specification returned three
results. Two were official Google support pages. The third was a marketing
blog. A system without tiers would have extracted "requirements" from all
three and presented them identically.

Under this policy the blog's claims are retained as context the user can read,
and can never become a rule anything is measured against.

## Severity is re-derived, never accepted

`build_rule()` takes the model's proposed severity and discards it if the
source does not support it:

- Tier D source → severity is forced to `context`, whatever the model claimed.
- `required` + `low` confidence → demoted to `recommended`, and surfaced for
  user confirmation rather than silently driving a verdict.

This is the end-to-end guarantee against prompt injection. A source page that
successfully convinces the model to emit `"severity": "required"` still cannot
produce a mandatory rule, because severity is overwritten by code that never
read the page.

## Injection handling

Retrieved text is wrapped in a fence keyed to the source's own content hash, so
text inside the block cannot forge a closing marker to escape into the
instruction context. The response schema has no field through which an
instruction could act: the model cannot emit a tier, a verdict, or an action.

Text matching instruction-shaped patterns is recorded and shown to the user.
It is not silently dropped — a destination page containing "ignore previous
instructions" is something the person delivering to that destination should
know about.

## Unstated requirements

If a destination does not publish a value, Preflight asserts nothing.

YouTube publishes no delivery loudness target. There are many blog posts
stating one. Preflight emits no loudness rule for YouTube, and a gap the user
can see is treated as strictly better than a number nobody published.

## Contradictions

When two Tier A sources disagree, the requirement becomes `AMBIGUOUS`, both
sources are shown with their retrieval dates, and readiness is blocked for
anything depending on it.

This is not hypothetical. Artdocfest publishes its technical requirements in
English and in Russian, and the two pages state different video bitrates. Live
extraction found it; nobody had to construct the case.

## Unreadable destinations

Some destinations publish authoritatively and unreadably. YouTube's encoding
specification is rendered by script: Parallel Extract returns 4 KB of prose
from it containing no bitrate, frame rate or aspect ratio at all. Netflix's
delivery specifications require partner login.

`machine_readability()` scores retrieved text and warns when an official page
yields almost nothing measurable. The product's answer for those destinations
is the Tier B path — the user supplies the specification they already have
access to, it is marked private, and it is never sent to any retrieval provider.
