"use client";

import Link from "next/link";
import { use, useCallback, useEffect, useState } from "react";

import { Shell } from "@/components/Shell";
import { StatusBadge } from "@/components/StatusBadge";
import { api, type PreflightRun } from "@/lib/api";
import type { AssertionResult } from "@/lib/types";

/**
 * The compatibility matrix.
 *
 * Rules this page follows, from the product principles:
 *  - every status links to the evidence behind it;
 *  - measured values sit beside published ones rather than being collapsed
 *    into a verdict;
 *  - the word "compliant" never appears. Readiness is stated as meeting
 *    published requirements, with the retrieval date attached.
 */
export default function PreflightPage({
  params,
}: {
  params: Promise<{ projectId: string }>;
}) {
  const { projectId } = use(params);
  return (
    <Shell>
      <Matrix projectId={projectId} />
    </Shell>
  );
}

function Matrix({ projectId }: { projectId: string }) {
  const [run, setRun] = useState<PreflightRun | null>(null);
  const [error, setError] = useState("");
  const [busy, setBusy] = useState(false);
  const [loaded, setLoaded] = useState(false);

  const load = useCallback(async () => {
    try {
      setRun(await api.latestPreflight(projectId));
    } catch {
      /* none yet — the user runs one below */
    } finally {
      setLoaded(true);
    }
  }, [projectId]);

  useEffect(() => {
    load();
  }, [load]);

  async function runNow() {
    setBusy(true);
    setError("");
    try {
      setRun(await api.runPreflight(projectId));
    } catch (e) {
      setError(e instanceof Error ? e.message : "Preflight could not run.");
    } finally {
      setBusy(false);
    }
  }

  if (!loaded) {
    return (
      <main className="mx-auto max-w-4xl px-6 py-12">
        <p className="text-neutral-500">Loading…</p>
      </main>
    );
  }

  return (
    <main className="mx-auto max-w-4xl px-6 py-10">
      <h1 className="text-2xl font-semibold text-neutral-100">
        What each destination requires
      </h1>
      <p className="mt-2 max-w-2xl text-sm text-neutral-400">
        Every requirement below was retrieved from the destination&apos;s own published
        documentation. Every measurement was taken from your files by ffprobe, ffmpeg
        and Pillow. Nothing here is inferred.
      </p>

      <div className="mt-5 flex flex-wrap items-center gap-3">
        <button
          onClick={runNow}
          disabled={busy}
          className="rounded bg-neutral-100 px-5 py-2 font-medium text-neutral-950
                     transition hover:bg-white disabled:opacity-50"
        >
          {busy ? "Measuring…" : run ? "Run preflight again" : "Run preflight"}
        </button>
        {run && (
          <span className="font-mono text-xs text-neutral-600">
            comparison digest {run.comparison_digest}
          </span>
        )}
      </div>

      {error && (
        <p role="alert" className="mt-5 text-sm text-rose-400">
          {error}
        </p>
      )}

      {!run && !error && (
        <p className="mt-8 text-sm text-neutral-400">
          No preflight has been run yet. Add your files and choose destinations, then
          run it.
        </p>
      )}

      {run && (
        <>
          {run.conflicts.length > 0 && (
            <div className="mt-8 space-y-3">
              <h2 className="text-sm font-medium uppercase tracking-wide text-neutral-500">
                Before anything else
              </h2>
              {run.conflicts.map((c, i) => (
                <ConflictCard key={i} conflict={c} />
              ))}
            </div>
          )}

          <div className="mt-8 space-y-6">
            {run.destinations.map((d) => {
              const failing = d.assertions.filter((a) => a.result !== "PASS");
              return (
                <section
                  key={d.destination_id}
                  className="rounded-lg border border-neutral-800 bg-neutral-950 p-5"
                >
                  <header className="flex flex-wrap items-baseline justify-between gap-2">
                    <h2 className="text-lg font-medium text-neutral-100">
                      {d.destination_id}
                    </h2>
                    <p className="text-sm text-neutral-400">
                      {d.satisfied} of {d.total} requirements met
                    </p>
                  </header>
                  <p className="mt-1 font-mono text-xs text-neutral-600">
                    rule pack {d.rule_pack_digest}
                  </p>
                  <p className="mt-3 text-sm">
                    {d.ready ? (
                      <span className="text-emerald-300">
                        Meets every published requirement Preflight could check.
                      </span>
                    ) : (
                      <span className="text-amber-300">
                        Not ready — {d.blocking.length} mandatory requirement
                        {d.blocking.length === 1 ? "" : "s"} outstanding.
                      </span>
                    )}
                  </p>

                  <ul className="mt-4">
                    {failing.map((a) => (
                      <li
                        key={a.rule_id}
                        className="border-b border-neutral-900 py-3 last:border-0"
                      >
                        <div className="flex flex-wrap items-baseline justify-between gap-2">
                          <span className="font-mono text-sm text-neutral-200">
                            {a.asset_type}.{a.field}
                          </span>
                          <StatusBadge result={a.result as AssertionResult} />
                        </div>
                        <dl className="mt-2 grid gap-x-6 gap-y-1 text-sm sm:grid-cols-2">
                          <div>
                            <dt className="inline text-neutral-500">Published: </dt>
                            <dd className="inline text-neutral-300">{a.published}</dd>
                          </div>
                          <div>
                            <dt className="inline text-neutral-500">Your file: </dt>
                            <dd className="inline font-medium text-neutral-100">
                              {a.measured === null ? "not measured" : String(a.measured)}
                            </dd>
                          </div>
                        </dl>
                        {a.explanation && (
                          <p className="mt-1.5 text-sm text-neutral-400">
                            {a.explanation}
                          </p>
                        )}
                        {a.source_url && (
                          <details className="mt-2 text-xs text-neutral-400">
                            <summary className="cursor-pointer text-neutral-500 hover:text-neutral-300">
                              Where this requirement comes from
                            </summary>
                            <div className="mt-2 border-l-2 border-neutral-800 pl-3">
                              {a.source_excerpt && (
                                <p className="italic text-neutral-300">
                                  {a.source_excerpt}
                                </p>
                              )}
                              <a
                                href={a.source_url}
                                target="_blank"
                                rel="noreferrer noopener"
                                className="mt-1 inline-block break-all text-sky-400 underline"
                              >
                                {a.source_url}
                              </a>
                              {a.retrieved_at && (
                                <p className="mt-1 text-neutral-500">
                                  Retrieved {a.retrieved_at}
                                </p>
                              )}
                            </div>
                          </details>
                        )}
                      </li>
                    ))}
                  </ul>

                  {failing.length === 0 && (
                    <p className="mt-4 text-sm text-neutral-400">Nothing outstanding.</p>
                  )}
                </section>
              );
            })}
          </div>

          {run.limitations.length > 0 && (
            <section className="mt-8 rounded-lg border border-neutral-800 p-4">
              <h2 className="text-sm font-medium text-neutral-300">
                What Preflight could not settle
              </h2>
              <ul className="mt-2 space-y-1 text-sm text-neutral-400">
                {run.limitations.map((l, i) => (
                  <li key={i}>{l}</li>
                ))}
              </ul>
            </section>
          )}

          <Link
            href={`/projects/${projectId}/plan`}
            className="mt-8 inline-block rounded bg-neutral-100 px-5 py-2 font-medium
                       text-neutral-950 transition hover:bg-white"
          >
            Review the repair plan
          </Link>
        </>
      )}

      <p className="mt-10 border-t border-neutral-900 pt-6 text-sm text-neutral-500">
        Preflight checks your files against what each destination publishes. It cannot
        promise that a festival or platform will accept your delivery.
      </p>
    </main>
  );
}

function ConflictCard({ conflict }: { conflict: Record<string, unknown> }) {
  const hard = conflict.strength === "hard";
  const destinations = (conflict.destinations as string[]) ?? [];
  const requirements = (conflict.requirements as string[]) ?? [];

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
          {String(conflict.assetType)}.{String(conflict.field)}
        </span>
      </p>
      <ul className="mt-3 space-y-1.5 text-sm">
        {destinations.map((d, i) => (
          <li key={d}>
            <span className="font-medium text-neutral-200">{d}</span>
            <span className="text-neutral-400"> requires {requirements[i]}</span>
          </li>
        ))}
      </ul>
      <p className="mt-3 text-sm text-neutral-400">
        {hard
          ? "Preflight builds a separate version for each. One file cannot go to both."
          : "One file can go to both, but one destination gets a result it does not recommend."}
      </p>
    </div>
  );
}
