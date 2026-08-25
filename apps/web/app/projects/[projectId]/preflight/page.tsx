import { StatusBadge } from "@/components/StatusBadge";
import type { Assertion, Conflict, DestinationMatrix, PreflightRun } from "@/lib/types";

/**
 * The compatibility matrix.
 *
 * Design rules this page follows, taken from the product principles:
 *  - every status links to the evidence behind it, so nothing is taken on trust;
 *  - measured values sit beside published ones rather than being collapsed into
 *    a verdict;
 *  - the word "compliant" never appears. Readiness is stated as meeting
 *    published requirements, with the retrieval date attached.
 */

async function getRun(projectId: string): Promise<PreflightRun | null> {
  const base = process.env.NEXT_PUBLIC_API_BASE_URL;
  if (!base) return null;
  const res = await fetch(`${base}/v1/projects/${projectId}/preflight/latest`, {
    cache: "no-store",
  });
  if (!res.ok) return null;
  return res.json();
}

function Evidence({ assertion }: { assertion: Assertion }) {
  if (!assertion.sourceUrl) return null;
  return (
    <details className="mt-2 text-xs text-neutral-400">
      <summary className="cursor-pointer text-neutral-500 hover:text-neutral-300">
        Where this requirement comes from
      </summary>
      <div className="mt-2 border-l-2 border-neutral-800 pl-3">
        {assertion.sourceExcerpt && (
          <p className="italic text-neutral-300">{assertion.sourceExcerpt}</p>
        )}
        <a
          href={assertion.sourceUrl}
          target="_blank"
          rel="noreferrer noopener"
          className="mt-1 inline-block break-all text-sky-400 underline underline-offset-2"
        >
          {assertion.sourceUrl}
        </a>
        {assertion.retrievedAt && (
          <p className="mt-1 text-neutral-500">Retrieved {assertion.retrievedAt}</p>
        )}
      </div>
    </details>
  );
}

function AssertionRow({ assertion }: { assertion: Assertion }) {
  return (
    <li className="border-b border-neutral-900 py-3 last:border-0">
      <div className="flex flex-wrap items-baseline justify-between gap-2">
        <span className="font-mono text-sm text-neutral-200">
          {assertion.assetType}.{assertion.field}
        </span>
        <StatusBadge result={assertion.result} />
      </div>

      <dl className="mt-2 grid gap-x-6 gap-y-1 text-sm sm:grid-cols-2">
        <div>
          <dt className="inline text-neutral-500">Published: </dt>
          <dd className="inline text-neutral-300">{assertion.published}</dd>
        </div>
        <div>
          <dt className="inline text-neutral-500">Your file: </dt>
          <dd className="inline font-medium text-neutral-100">
            {assertion.measured === null ? "not measured" : String(assertion.measured)}
          </dd>
        </div>
      </dl>

      {assertion.explanation && (
        <p className="mt-1.5 text-sm text-neutral-400">{assertion.explanation}</p>
      )}
      <Evidence assertion={assertion} />
    </li>
  );
}

function ConflictCard({ conflict }: { conflict: Conflict }) {
  const hard = conflict.strength === "hard";
  return (
    <div
      className={`rounded-lg border p-4 ${
        hard ? "border-rose-900 bg-rose-950/30" : "border-amber-900 bg-amber-950/20"
      }`}
    >
      <p className="text-sm font-medium text-neutral-100">
        {hard
          ? "These destinations cannot both be satisfied"
          : "These destinations disagree"}
        <span className="ml-2 font-mono text-xs text-neutral-400">
          {conflict.assetType}.{conflict.field}
        </span>
      </p>

      <ul className="mt-3 space-y-2 text-sm">
        {conflict.destinations.map((destination, i) => (
          <li key={destination}>
            <span className="font-medium text-neutral-200">{destination}</span>
            <span className="text-neutral-400"> requires {conflict.requirements[i]}</span>
            {conflict.excerpts?.[i] && (
              <p className="mt-0.5 border-l-2 border-neutral-800 pl-3 text-xs italic text-neutral-400">
                {conflict.excerpts[i]}
              </p>
            )}
            {conflict.evidenceUrls?.[i] && (
              <a
                href={conflict.evidenceUrls[i]}
                target="_blank"
                rel="noreferrer noopener"
                className="mt-0.5 block break-all pl-3 text-xs text-sky-400 underline"
              >
                {conflict.evidenceUrls[i]}
              </a>
            )}
          </li>
        ))}
      </ul>

      <p className="mt-3 text-sm text-neutral-400">
        {hard
          ? "Preflight will build a separate version for each. One file cannot go to both."
          : "One file can go to both, but one destination gets a result it does not recommend."}
      </p>
    </div>
  );
}

function DestinationSection({ matrix }: { matrix: DestinationMatrix }) {
  const failing = matrix.assertions.filter((a) => a.result !== "PASS");
  const satisfied = matrix.assertions.length - failing.length;

  return (
    <section className="rounded-lg border border-neutral-800 bg-neutral-950 p-5">
      <header className="flex flex-wrap items-baseline justify-between gap-2">
        <h2 className="text-lg font-medium text-neutral-100">{matrix.destinationName}</h2>
        <p className="text-sm text-neutral-400">
          {satisfied} of {matrix.assertions.length} requirements met
        </p>
      </header>

      <p className="mt-1 text-xs text-neutral-500">
        Rule pack v{matrix.rulePackVersion} · {matrix.rulePackDigest}
      </p>

      <p className="mt-3 text-sm">
        {matrix.ready ? (
          <span className="text-emerald-300">
            Meets every published requirement Preflight could check.
          </span>
        ) : (
          <span className="text-amber-300">
            Not ready — {failing.length} requirement{failing.length === 1 ? "" : "s"}{" "}
            outstanding.
          </span>
        )}
      </p>

      <ul className="mt-4">
        {failing.map((a) => (
          <AssertionRow key={`${matrix.destinationId}-${a.ruleId}`} assertion={a} />
        ))}
      </ul>

      {failing.length === 0 && (
        <p className="mt-4 text-sm text-neutral-400">Nothing outstanding.</p>
      )}
    </section>
  );
}

export default async function PreflightPage({
  params,
}: {
  params: Promise<{ projectId: string }>;
}) {
  const { projectId } = await params;
  const run = await getRun(projectId);

  if (!run) {
    return (
      <main className="mx-auto max-w-3xl px-6 py-16">
        <h1 className="text-2xl font-semibold text-neutral-100">Preflight</h1>
        <p className="mt-4 text-neutral-400">
          No preflight has been run for this project yet. Add your master and choose
          destinations first.
        </p>
      </main>
    );
  }

  return (
    <main className="mx-auto max-w-4xl px-6 py-12">
      <h1 className="text-2xl font-semibold text-neutral-100">
        What each destination requires
      </h1>
      <p className="mt-2 max-w-2xl text-neutral-400">
        Every requirement below was retrieved from the destination&apos;s own published
        documentation, and every measurement was taken from your files by ffprobe,
        ffmpeg and Pillow. Nothing here is inferred.
      </p>
      <p className="mt-1 font-mono text-xs text-neutral-600">
        comparison digest {run.comparisonDigest}
      </p>

      {run.conflicts.length > 0 && (
        <div className="mt-8 space-y-3">
          <h2 className="text-sm font-medium uppercase tracking-wide text-neutral-500">
            Before anything else
          </h2>
          {run.conflicts.map((c) => (
            <ConflictCard key={`${c.assetType}.${c.field}`} conflict={c} />
          ))}
        </div>
      )}

      <div className="mt-8 space-y-6">
        {run.destinations.map((m) => (
          <DestinationSection key={m.destinationId} matrix={m} />
        ))}
      </div>

      <p className="mt-10 border-t border-neutral-900 pt-6 text-sm text-neutral-500">
        Preflight checks your files against what each destination publishes. It cannot
        promise that a festival or platform will accept your delivery.
      </p>
    </main>
  );
}
