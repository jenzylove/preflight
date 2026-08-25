# Data retention and deletion

## What Preflight stores

| Data | Where | Retained until |
|---|---|---|
| Original master, subtitles, poster | Private Cloud Storage | The user deletes them |
| Derived assets | Private Cloud Storage | The user deletes them |
| Packages | Private Cloud Storage | The user deletes them |
| Temporary working files | `temporary/` prefix | Automatically removed after 1 day |
| Measurements, rules, assertions | PostgreSQL | Project lifetime |
| Passports | PostgreSQL | Project lifetime; immutable once issued |
| Delivery token hashes | PostgreSQL | Room lifetime |

Originals are **never** deleted on a timer. A producer's master disappearing on
a schedule they did not set would be a betrayal of the reason they uploaded it.
Only `temporary/` expires automatically.

## Deletion

Deletion is asynchronous and reports real progress.

1. The project moves to `DELETION_PENDING` immediately, so nothing further can
   be built from it.
2. A deletion request records how many objects must go.
3. A worker removes them and increments the count as it goes.
4. Only when every object is gone does the project become `DELETED`.

The UI shows pending, running, completed or failed — never "deleted" before the
bytes are actually gone. Reporting completion early would misrepresent the one
thing users most need to trust.

Deletion is idempotent: an object already missing counts as success.

## What survives deletion

Operational records with no media and no filenames: that a project existed,
when it was deleted, and how many objects were removed. This is the minimum
needed to prove a deletion was carried out.

Passports issued before deletion retain their hashes. A hash is not the
content, and a delivery receipt whose evidence vanished would be worthless to
the person holding it.

## What leaves the system

| Destination | What is sent | What is never sent |
|---|---|---|
| Parallel | Destination names and public spec URLs | Any media. Any private specification. Any project detail |
| Vertex AI (Gemini) | Retrieved public specification text | Any media. Any private specification |
| Cloud Storage | Media, encrypted at rest, private | — |

Private specifications are marked private in the database, and the schema
enforces it: a `CHECK` constraint requires a private source to have an owner
and no public URL.

## Claims not yet verified

Stated plainly rather than implied:

- Whether provider terms permit the retained specification text to be used for
  model training.
- Exact provider retention windows.
- Backup deletion windows for Cloud SQL.

These are not presented as product promises anywhere in the interface, and
should not be until provider terms and the actual configuration prove them.
