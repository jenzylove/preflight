"use client";

import Link from "next/link";
import { use, useCallback, useEffect, useState } from "react";

import { Shell } from "@/components/Shell";
import { api, type PlanStep, type PreflightRun } from "@/lib/api";

/**
 * The repair plan and its approval.
 *
 * Approval is bound to the plan digest shown on this page. If anything about
 * the plan changes, the digest changes and the approval no longer matches — so
 * the digest is displayed rather than hidden, and it is what the user is
 * actually agreeing to.
 *
 * Green steps can be deselected. Yellow and red steps cannot be selected at
 * all: they are shown so the user knows what would be required, and Preflight
 * refuses to perform them rather than doing them quietly.
 */
export default function PlanPage({
  params,
}: {
  params: Promise<{ projectId: string }>;
}) {
  const { projectId } = use(params);
  return (
    <Shell>
      <PlanView projectId={projectId} />
    </Shell>
  );
}

const SAFETY_COPY = {
  green: {
    label: "Preflight will do this",
    detail: "Deterministic and non-destructive. Runs only after you approve.",
    ring: "ring-emerald-800 bg-emerald-950/30",
  },
  yellow: {
    label: "Needs your decision",
    detail:
      "This changes the picture or the meaning. Preflight will not do it automatically.",
    ring: "ring-amber-800 bg-amber-950/20",
  },
  red: {
    label: "Preflight cannot do this",
    detail: "Requires professional work or authority Preflight does not have.",
    ring: "ring-rose-800 bg-rose-950/20",
  },
} as const;

function PlanView({ projectId }: { projectId: string }) {
  const [run, setRun] = useState<PreflightRun | null>(null);
  const [selected, setSelected] = useState<Set<string>>(new Set());
  const [error, setError] = useState("");
  const [busy, setBusy] = useState(false);
  const [jobId, setJobId] = useState<string | null>(null);
  const [jobState, setJobState] = useState<string>("");
  const [jobMessage, setJobMessage] = useState<string>("");

  const load = useCallback(async () => {
    try {
      const latest = await api.latestPreflight(projectId);
      setRun(latest);
      setSelected(
        new Set(latest.plan.steps.filter((s) => s.executable).map((s) => s.step_id)),
      );
    } catch (e) {
      setError(e instanceof Error ? e.message : "Could not load the plan.");
    }
  }, [projectId]);

  useEffect(() => {
    load();
  }, [load]);

  // Poll the real job. No simulated progress: the state shown is the state the
  // API reports, and a job that fails says so.
  useEffect(() => {
    if (!jobId) return;
    let stop = false;
    const tick = async () => {
      try {
        const s = await api.jobStatus(projectId, jobId);
        if (stop) return;
        setJobState(s.state);
        setJobMessage(s.message);
        if (s.state === "QUEUED" || s.state === "RUNNING") setTimeout(tick, 3000);
      } catch {
        if (!stop) setTimeout(tick, 5000);
      }
    };
    tick();
    return () => {
      stop = true;
    };
  }, [jobId, projectId]);

  async function approveAndRun() {
    if (!run?.plan.plan_id) return;
    setBusy(true);
    setError("");
    try {
      await api.approvePlan(projectId, run.plan.plan_id, run.plan.digest, [...selected]);
      const job = await api.executePlan(projectId, run.plan.plan_id);
      setJobId(job.job_id);
      setJobState(job.state);
      setJobMessage(job.message);
    } catch (e) {
      setError(e instanceof Error ? e.message : "Could not start processing.");
    } finally {
      setBusy(false);
    }
  }

  if (error && !run) {
    return (
      <main className="mx-auto max-w-3xl px-6 py-12">
        <p className="text-rose-400">{error}</p>
        <Link
          href={`/projects/${projectId}/preflight`}
          className="mt-4 inline-block text-sky-400 underline"
        >
          Run preflight first
        </Link>
      </main>
    );
  }

  if (!run) {
    return (
      <main className="mx-auto max-w-3xl px-6 py-12">
        <p className="text-neutral-500">Loading the plan…</p>
      </main>
    );
  }

  const green = run.plan.steps.filter((s) => s.safety === "green");
  const other = run.plan.steps.filter((s) => s.safety !== "green");
  const finished = jobState === "SUCCEEDED" || jobState === "FAILED";

  return (
    <main className="mx-auto max-w-3xl px-6 py-10">
      <h1 className="text-2xl font-semibold text-neutral-100">
        What Preflight proposes to do
      </h1>
      <p className="mt-2 text-sm text-neutral-400">
        Your original files are never modified. Every operation writes a new file.
      </p>
      <p className="mt-1 font-mono text-xs text-neutral-600">
        plan digest {run.plan.digest}
      </p>

      {run.plan.preserved_assets.length > 0 && (
        <p className="mt-4 rounded border border-neutral-800 bg-neutral-900/40 p-3 text-sm text-neutral-300">
          Untouched by this plan:{" "}
          <span className="text-neutral-100">
            {run.plan.preserved_assets.join(", ")}
          </span>
        </p>
      )}

      <section className="mt-8">
        <h2 className="text-sm font-medium uppercase tracking-wide text-neutral-500">
          Safe operations
        </h2>
        {green.length === 0 && (
          <p className="mt-3 text-sm text-neutral-400">
            Nothing here can be repaired automatically.
          </p>
        )}
        <ul className="mt-3 space-y-3">
          {green.map((step) => (
            <StepCard
              key={step.step_id}
              step={step}
              checked={selected.has(step.step_id)}
              onToggle={() =>
                setSelected((s) => {
                  const next = new Set(s);
                  next.has(step.step_id)
                    ? next.delete(step.step_id)
                    : next.add(step.step_id);
                  return next;
                })
              }
            />
          ))}
        </ul>
      </section>

      {other.length > 0 && (
        <section className="mt-8">
          <h2 className="text-sm font-medium uppercase tracking-wide text-neutral-500">
            Preflight will not do these
          </h2>
          <ul className="mt-3 space-y-3">
            {other.map((step) => (
              <StepCard key={step.step_id} step={step} />
            ))}
          </ul>
        </section>
      )}

      {run.plan.blocked.length > 0 && (
        <section className="mt-8 rounded-lg border border-rose-900 bg-rose-950/20 p-4">
          <h2 className="text-sm font-medium text-neutral-100">Blocked</h2>
          <ul className="mt-2 space-y-1 text-sm text-neutral-400">
            {run.plan.blocked.map((b, i) => (
              <li key={i}>
                <span className="font-mono text-neutral-300">{String(b.field)}</span>{" "}
                — {String(b.reason ?? "")}
              </li>
            ))}
          </ul>
        </section>
      )}

      {error && (
        <p role="alert" className="mt-6 text-sm text-rose-400">
          {error}
        </p>
      )}

      <div className="mt-8 flex flex-wrap items-center gap-3">
        <button
          onClick={approveAndRun}
          disabled={busy || selected.size === 0 || Boolean(jobId)}
          className="rounded bg-neutral-100 px-5 py-2 font-medium text-neutral-950
                     transition hover:bg-white disabled:opacity-40"
        >
          {busy
            ? "Starting…"
            : `Approve ${selected.size} operation${selected.size === 1 ? "" : "s"} and run`}
        </button>
        {run.plan.estimated_seconds > 0 && !jobId && (
          <span className="text-sm text-neutral-500">
            about {run.plan.estimated_seconds}s of processing
          </span>
        )}
      </div>

      {jobId && (
        <div className="mt-6 rounded-lg border border-neutral-800 p-4">
          <p className="text-sm text-neutral-300">
            <span className="font-mono text-xs text-neutral-500">{jobState}</span>{" "}
            — {jobMessage}
          </p>
          {!finished && (
            <p className="mt-2 text-xs text-neutral-500">
              The worker fetches your files from private storage, performs only the
              operations you approved, then measures what it produced.
            </p>
          )}
          {finished && (
            <Link
              href={`/projects/${projectId}/packages`}
              className="mt-3 inline-block rounded bg-neutral-100 px-4 py-2 text-sm
                         font-medium text-neutral-950 hover:bg-white"
            >
              See the packages
            </Link>
          )}
        </div>
      )}
    </main>
  );
}

function StepCard({
  step,
  checked,
  onToggle,
}: {
  step: PlanStep;
  checked?: boolean;
  onToggle?: () => void;
}) {
  const copy = SAFETY_COPY[step.safety];
  const selectable = step.executable && onToggle;

  return (
    <li className={`rounded-lg p-4 ring-1 ring-inset ${copy.ring}`}>
      <div className="flex items-start gap-3">
        {selectable && (
          <input
            type="checkbox"
            checked={checked}
            onChange={onToggle}
            className="mt-1 h-4 w-4"
            aria-label={`Approve ${step.operation}`}
          />
        )}
        <div className="min-w-0 flex-1">
          <div className="flex flex-wrap items-baseline justify-between gap-2">
            <span className="font-mono text-sm text-neutral-100">{step.operation}</span>
            <span className="text-xs text-neutral-400">{copy.label}</span>
          </div>
          <p className="mt-1 text-sm text-neutral-300">{step.explains}</p>
          <p className="mt-1 text-xs text-neutral-500">{copy.detail}</p>
          <p className="mt-2 text-xs text-neutral-500">
            for {step.destination_id} · reads {step.input_role} · writes{" "}
            {step.output_role}
          </p>
          {Object.keys(step.parameters).length > 0 && (
            <dl className="mt-2 flex flex-wrap gap-x-4 gap-y-1 text-xs">
              {Object.entries(step.parameters).map(([k, v]) => (
                <div key={k}>
                  <dt className="inline text-neutral-500">{k}: </dt>
                  <dd className="inline text-neutral-300">{String(v)}</dd>
                </div>
              ))}
            </dl>
          )}
        </div>
      </div>
    </li>
  );
}
