# Threat model

Preflight holds unreleased films. The worst outcome is not downtime — it is a
festival cut appearing somewhere it should not, or a producer trusting a
verdict that was wrong.

## Assets, in order of what their loss costs

1. **Unreleased media.** Irreversible. A leaked cut cannot be un-leaked.
2. **Verification verdicts.** A false "ready" causes a rejection the user was
   told would not happen, at the point where it is most expensive.
3. **Delivery links.** A working link is equivalent to the media behind it.
4. **Private specifications.** Often under NDA with the destination.

## Threats and what actually stops them

### Media disclosure

| Threat | Control |
|---|---|
| Public bucket | `public_access_prevention = enforced`, uniform bucket-level access |
| Long-lived URLs | Signed URLs expire in 15 minutes; no other read path exists |
| Cross-project access | Every query is owner-scoped; wrong owner returns 404, never 403 |
| Guessed delivery links | 32 random bytes, stored only as a hash, constant-time comparison |
| Leaked database | Token hashes are not tokens. A dump yields no working links |
| Bucket paths in the UI | Delivery responses carry an allowlist of fields; storage keys are not in it |
| Worker disk residue | Scratch space is a temporary directory removed even when a job fails |

A 403 confirms a resource exists. That is enough to enumerate other people's
projects, so authorisation failures are indistinguishable from absence.

### False verification

The most dangerous failure is a package marked ready that is not.

- The worker has **no transition into `VERIFIED`**. `BUILDING → VERIFIED` does
  not exist as an edge; every route passes through independent validation.
- Validation re-measures the built package from disk. It shares no state with
  the executor.
- `validated_against_output` is set in one place, and the database refuses to
  store a verified package without it.
- The manifest is recomputed, and files added after it was written are detected.

A worker that exits zero having produced a broken poster cannot mark anything
verified.

### Invented requirements

Covered in full by [rule-source-policy.md](rule-source-policy.md). In summary:
tier is assigned from the URL in Python, severity is re-derived after the model
returns, and no Tier D source can produce a mandatory rule regardless of what
the model claims about it.

### Malicious media and archives

| Threat | Control |
|---|---|
| Path traversal in filenames | `safe_package_name()` **rejects** `..` and absolute paths rather than rewriting them |
| Null bytes | Rejected |
| Disguised file types | Content is measured by ffprobe/Pillow; extension is only the first gate |
| Oversized uploads | Per-role byte limits enforced before a signed URL is issued |
| Shell injection via filenames | Media tools are invoked as argument lists, never through a shell |
| Unbounded processing | Cloud Run timeout, concurrency 1, max 5 instances, 5 retry attempts |

A filename containing `..` is treated as a signal, not a typo. Sanitising it
quietly would discard evidence that someone is probing.

### Unauthorised transformation

- Execution requires a stored approval whose digest matches the current plan.
  Change any parameter and the digest changes and the approval no longer
  matches.
- Only `green` operations execute. A `yellow` step reaching the worker is
  refused, not run.
- Operations outside the catalogue are refused.
- Originals are immutable; every repair writes a new file.

### Credential compromise

The runtime service account holds `storage.objectAdmin`, not
`storage.admin` — it can read and write objects but cannot reconfigure or
delete buckets, so a compromised runtime cannot widen its own access.

Secrets come from Secret Manager. Preflight names its own credential
explicitly rather than inheriting `GOOGLE_APPLICATION_CREDENTIALS` from the
machine, because a machine-wide value pointing at another project surfaces as
a permissions error rather than the wrong-identity error it actually is. That
mistake happened once during development and cost real time to diagnose.

## What is deliberately not logged

No filenames, no media URLs, no bucket paths, no tokens, no IP addresses, no
user agents. Delivery events record that a download occurred; the owner needs
to know it happened, not to be handed a surveillance log about their recipient.

Rejected authentication tokens are logged as rejections without the token. A
rejected token in a log file is still a credential.

## Accepted risks

- **Single-region storage.** No cross-region redundancy at this scale.
- **Signed URL forwarding.** A recipient can pass a valid URL to someone else
  within its 15-minute life. Shortening it further would break large downloads.
- **No malware scanning.** Uploads are validated structurally, not scanned.
- **Vertex AI retention.** Requirement *text* is sent to Gemini. Media never
  is. Provider retention terms are not independently verified, and this is
  stated rather than glossed.
