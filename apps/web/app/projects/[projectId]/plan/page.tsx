"use client";

import Link from "next/link";
import { use, useCallback, useEffect, useRef, useState } from "react";

import { SAFETY, SafetyChip, StatusChip, Working } from "@/components/Status";
import { ProjectRail } from "@/components/workspace/Rail";
import { Workspace } from "@/components/workspace/Workspace";
import { api } from "@/lib/api";
import type { JobStatus, PlanStep, PreflightRun, Project } from "@/lib/types";

/**
 * The repair plan, the approval, and the work itself.
 *
 * Three rules shape this screen. Everything Preflight would do is shown, not
 * just the parts that are convenient. Nothing runs until the user approves the
 * exact plan in front of them. And what the operations leave alone is stated
 * as plainly as what they change, because that is a producer's first question
 * about anything automatic touching their film.
 *
 * There is deliberately no "fix everything" button.
 */
export default function PlanPage({
  params,
}: {
  params: Promise<{ projectId: string }>;
}) {
  const { projectId } = use(params);
  return (
    <Workspace wide>
      <PlanView projectId={projectId} />
    </Workspace>
  );
}

function PlanView({ projectId }: { projectId: string }) {
  const [project, setProject] = useState<Project | null>(null);
  const [run, setRun] = useState<PreflightRun | null>(null);
  const [job, setJob] = useState<JobStatus | null>(null);
  const [approved, setApproved] = useState(false);
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const polling = useRef<ReturnType<typeof setInterval> | null>(null);

  const load = useCallback(async () => {
    const [p, latest] = await Promise.all([
      api.getProject(projectId),
      api.latestPreflight(projectId).catch(() => null),
    ]);
    setProject(p);
    setRun(latest);
  }, [projectId]);

  useEffect(() => {
    load().catch((caught) =>
      setError(caught instanceof Error ? caught.message : "Could not load the plan."),
    );
  }, [load]);

  // Job state is polled because the backend reports state, not progress. Once
  // it reaches a terminal state the polling stops rather than running forever.
  useEffect(() => {
    if (!job || ["SUCCEEDED", "FAILED", "CANCELLED"].includes(job.state)) {
      if (polling.current) clearInterval(polling.current);
      return;
    }
    polling.current = setInterval(async () => {
      try {
        setJob(await api.jobStatus(projectId, job.job_id));
      } catch {
        /* a dropped poll is not a failed job; the next one will tell us */
      }
    }, 4000);
    return () => {
      if (polling.current) clearInterval(polling.current);
    };
  }, [job, projectId]);

  const plan = run?.plan;
  const green = plan?.steps ?? [];
  const yellow = plan?.needs_your_decision ?? [];
  const blocked = plan?.blocked ?? [];
  const unresolved = plan?.unresolved ?? [];

  async function approveAndRun() {
    if (!plan?.plan_id) return;
    setBusy(true);
    setError(null);
    try {
      await api.approvePlan(
        projectId,
        plan.plan_id,
        plan.digest,
        green.map((step) => step.step_id),
      );
      setApproved(true);
      const started = await api.executePlan(projectId, plan.plan_id);
      setJob(await api.jobStatus(projectId, started.job_id));
    } catch (caught) {
      setError(
        caught instanceof Error ? caught.message : "The repairs did not start.",
      );
    } finally {
      setBusy(false);
    }
  }

  if (!project) {
    return <p className="slate text-paper-400" role="status">Loading</p>;
  }

  if (!plan) {
    return (
      <>
        <ProjectRail project={project} />
        <p className="text-paper-300">
          There is no repair plan yet. Run preflight first.
        </p>
      </>
    );
  }

  const finished = job?.state === "SUCCEEDED";

  return (
    <>
      <ProjectRail project={project} />

      <div className="mb-8">
        <h2 className="font-display text-2xl text-paper-000">
          What Preflight proposes to do
        </h2>
        <p className="mt-3 max-w-measure text-[15px] leading-relaxed text-paper-300">
          Your original master is never written to. Every operation below writes
          a new file, and anything that could change the picture, the timing or
          the meaning of the work is yours to decide rather than Preflight&rsquo;s.
        </p>
      </div>

      {job ? (
        <Processing job={job} steps={green} projectId={projectId} finished={finished} />
      ) : (
        <>
          {green.length > 0 && (
            <Group
              title="Preflight will do this"
              note={SAFETY.green.note}
              steps={green}
            />
          )}

          {yellow.length > 0 && (
            <Group
              title="Your decision"
              note={SAFETY.yellow.note}
              steps={yellow}
            />
          )}

          {(blocked.length > 0 || unresolved.length > 0) && (
            <section className="mt-10">
              <h3 className="slate mb-1 text-paper-400">
                Preflight will not do this
              </h3>
              <p className="mb-4 max-w-measure text-sm text-paper-400">
                {SAFETY.red.note}
              </p>
              <ul className="space-y-2">
                {[...blocked, ...unresolved].map((item, index) => (
                  <li
                    key={index}
                    className="rounded-[3px] border-l-2 border-stop bg-stop-bg/25 px-4 py-3"
                  >
                    <p className="font-mono text-sm text-paper-100">
                      {String(item.field ?? item.destination ?? "requirement")}
                    </p>
                    <p className="mt-1 text-sm text-paper-300">
                      {String(item.reason ?? "")}
                    </p>
                  </li>
                ))}
              </ul>
            </section>
          )}

          {plan.preserved_assets.length > 0 && (
            <p className="mt-8 rounded-[3px] border border-line bg-ink-100 px-4 py-3 text-sm text-paper-300">
              <span className="text-paper-100">Left untouched:</span>{" "}
              {plan.preserved_assets.join(", ")}
            </p>
          )}

          {green.length > 0 && (
            <Approve
              plan={plan}
              stepCount={green.length}
              busy={busy}
              approved={approved}
              onApprove={approveAndRun}
            />
          )}

          {green.length === 0 && (
            <p className="mt-8 text-paper-300">
              There is nothing here Preflight can safely do on its own.
            </p>
          )}
        </>
      )}

      {error && (
        <p role="alert" className="mt-6 border-l-2 border-stop bg-stop-bg/40 py-3 pl-4 text-paper-100">
          {error}
        </p>
      )}
    </>
  );
}

function Group({
  title,
  note,
  steps,
}: {
  title: string;
  note: string;
  steps: PlanStep[];
}) {
  return (
    <section className="mt-10 first:mt-0">
      <h3 className="slate mb-1 text-paper-400">{title}</h3>
      <p className="mb-4 max-w-measure text-sm text-paper-400">{note}</p>
      <ul className="space-y-3">
        {steps.map((step) => (
          <li key={step.step_id}>
            <StepCard step={step} />
          </li>
        ))}
      </ul>
    </section>
  );
}

function StepCard({ step }: { step: PlanStep }) {
  return (
    <div className="rounded-[3px] border border-line bg-ink-100 p-5">
      <div className="flex flex-wrap items-baseline justify-between gap-3">
        <h4 className="font-mono text-sm text-paper-000">{step.operation}</h4>
        <SafetyChip safety={step.safety} />
      </div>

      <p className="mt-2.5 max-w-measure text-sm leading-relaxed text-paper-200">
        {step.what_it_does}
      </p>

      <dl className="mt-4 grid gap-x-8 gap-y-1.5 text-xs sm:grid-cols-2">
        {step.input_asset && (
          <Detail label="Reads" value={step.input_asset} />
        )}
        <Detail label="Writes" value={step.output} />
        {step.resolves.length > 0 && (
          <Detail
            label="Because"
            value={`${step.resolves.length} requirement${step.resolves.length === 1 ? "" : "s"}`}
          />
        )}
        {Object.entries(step.parameters).map(([key, value]) => (
          <Detail key={key} label={key} value={String(value)} mono />
        ))}
      </dl>

      {!step.executable && (
        <p className="mt-4 border-l-2 border-review bg-review-bg/25 py-2.5 pl-3 text-sm text-paper-200">
          Preflight will not run this on its own, even with your approval. It
          needs a person to decide what the result should look like.
        </p>
      )}
    </div>
  );
}

function Detail({
  label,
  value,
  mono,
}: {
  label: string;
  value: string;
  mono?: boolean;
}) {
  return (
    <div className="flex items-baseline justify-between gap-3 border-b border-line/60 pb-1">
      <dt className="text-paper-400">{label}</dt>
      <dd className={`text-right text-paper-100 ${mono ? "font-mono" : ""}`}>
        {value}
      </dd>
    </div>
  );
}

/**
 * Approval.
 *
 * The digest travels with the consent, so if the plan changes between being
 * shown and being approved the server refuses. It is not the headline of the
 * interaction — a producer approves work, not a hash — but it is visible for
 * anyone who wants to check.
 */
function Approve({
  plan,
  stepCount,
  busy,
  approved,
  onApprove,
}: {
  plan: PreflightRun["plan"];
  stepCount: number;
  busy: boolean;
  approved: boolean;
  onApprove: () => void;
}) {
  const seconds = plan.estimated_seconds;

  return (
    <div className="mt-10 rounded-[3px] border border-line-strong bg-ink-100 p-6">
      <h3 className="font-display text-lg text-paper-000">
        Approve {stepCount} operation{stepCount === 1 ? "" : "s"}
      </h3>
      <p className="mt-2 max-w-measure text-sm leading-relaxed text-paper-300">
        You are approving exactly the operations listed above. If anything about
        this plan changes, this approval stops applying and Preflight will ask
        again.
        {seconds != null && seconds > 0 && (
          <> Expected to take about {formatDuration(seconds)}.</>
        )}
      </p>

      <div className="mt-5 flex flex-wrap items-center gap-4">
        <button
          type="button"
          onClick={onApprove}
          disabled={busy || approved}
          className="rounded-[3px] bg-paper-000 px-5 py-2.5 text-sm font-medium
                     text-ink-000 transition hover:bg-white disabled:opacity-50"
        >
          {busy ? "Starting…" : "Approve and run"}
        </button>
        <details className="text-xs text-paper-400">
          <summary className="cursor-pointer hover:text-paper-200">
            What is being signed
          </summary>
          <p className="mt-2 font-mono break-all text-paper-300">{plan.digest}</p>
          <p className="mt-1 max-w-measure">
            This identifies the exact plan. It changes if any parameter of any
            operation changes.
          </p>
        </details>
      </div>
    </div>
  );
}

/**
 * The work running.
 *
 * Job state comes from the backend, which reports a state rather than a
 * fraction, so this shows the stage it is genuinely in. A bar creeping toward
 * ninety percent and waiting there would be an invention.
 */
function Processing({
  job,
  steps,
  projectId,
  finished,
}: {
  job: JobStatus;
  steps: PlanStep[];
  projectId: string;
  finished: boolean;
}) {
  const failed = job.state === "FAILED" || job.state === "CANCELLED";

  return (
    <section className="rounded-[3px] border border-line bg-ink-100 p-6">
      <div className="flex flex-wrap items-baseline justify-between gap-3">
        <h3 className="font-display text-lg text-paper-000">
          {finished
            ? "Repairs finished"
            : failed
              ? "Processing stopped"
              : "Working on your files"}
        </h3>
        <StatusChip tone={finished ? "ok" : failed ? "stop" : "think"}>
          {job.state.toLowerCase()}
        </StatusChip>
      </div>

      <p className="mt-3 max-w-measure text-sm leading-relaxed text-paper-300">
        {job.message}
      </p>

      {!finished && !failed && (
        <div className="mt-5">
          <Working label="Running the approved operations" />
          <ul className="mt-4 space-y-1.5">
            {steps.map((step) => (
              <li key={step.step_id} className="font-mono text-xs text-paper-400">
                {step.operation}
              </li>
            ))}
          </ul>
        </div>
      )}

      {finished && (
        <>
          <p className="mt-5 max-w-measure text-sm leading-relaxed text-paper-200">
            The worker reported success, which on its own proves only that a
            process ended. Preflight has re-opened the files it produced and
            measured them again from scratch.
          </p>
          <Link
            href={`/projects/${projectId}/packages`}
            className="mt-5 inline-flex rounded-[3px] bg-paper-000 px-5 py-2.5 text-sm
                       font-medium text-ink-000 transition hover:bg-white"
          >
            See what the recheck found
          </Link>
        </>
      )}

      {failed && (
        <p className="mt-4 border-l-2 border-stop bg-stop-bg/30 py-3 pl-4 text-sm text-paper-100">
          Your original files are untouched. Nothing was marked ready.
        </p>
      )}
    </section>
  );
}

function formatDuration(seconds: number): string {
  if (seconds < 90) return `${seconds} seconds`;
  return `${Math.round(seconds / 60)} minutes`;
}
