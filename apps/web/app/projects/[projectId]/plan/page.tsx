"use client";

import Link from "next/link";
import { use, useCallback, useEffect, useRef, useState } from "react";

import { StatusChip, Working } from "@/components/Status";
import { ProjectRail } from "@/components/workspace/Rail";
import { Workspace } from "@/components/workspace/Workspace";
import { api } from "@/lib/api";
import {
  fieldLabel,
  formatValue,
  operationLabel,
  requirementAction,
  requirementSentence,
  whatYouCanDo,
} from "@/lib/language";
import type {
  Assertion,
  JobStatus,
  Plan,
  PlanStep,
  PreflightRun,
  Project,
  Rule,
} from "@/lib/types";

type PlanEntry = Record<string, unknown>;
type Finding = {
  assertion?: Assertion;
  rule?: Rule;
  destination: string;
  assetType: string;
  field: string;
};

export default function PlanPage({
  params,
}: {
  params: Promise<{ projectId: string }>;
}) {
  const { projectId } = use(params);
  return <Workspace wide><PlanView projectId={projectId} /></Workspace>;
}

function PlanView({ projectId }: { projectId: string }) {
  const [project, setProject] = useState<Project | null>(null);
  const [run, setRun] = useState<PreflightRun | null>(null);
  const [rules, setRules] = useState<Rule[]>([]);
  const [names, setNames] = useState<Record<string, string>>({});
  const [job, setJob] = useState<JobStatus | null>(null);
  const [approved, setApproved] = useState(false);
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const polling = useRef<ReturnType<typeof setInterval> | null>(null);

  const load = useCallback(async () => {
    const [p, latest, ruleList, destinations] = await Promise.all([
      api.getProject(projectId),
      api.latestPreflight(projectId).catch(() => null),
      api.listRules(projectId).catch(() => [] as Rule[]),
      api.listDestinations().catch(() => []),
    ]);
    setProject(p);
    setRun(latest);
    setRules(ruleList);
    setNames(Object.fromEntries(destinations.map((d) => [d.slug, d.name])));
  }, [projectId]);

  useEffect(() => {
    load().catch((caught) =>
      setError(caught instanceof Error ? caught.message : "Could not load the plan."),
    );
  }, [load]);

  useEffect(() => {
    if (!job || ["SUCCEEDED", "FAILED", "CANCELLED"].includes(job.state)) {
      if (polling.current) clearInterval(polling.current);
      return;
    }
    polling.current = setInterval(async () => {
      try { setJob(await api.jobStatus(projectId, job.job_id)); } catch { /* retry */ }
    }, 4000);
    return () => { if (polling.current) clearInterval(polling.current); };
  }, [job, projectId]);

  async function applySafeFixes() {
    const plan = run?.plan;
    if (!plan?.plan_id) return;
    setBusy(true);
    setError(null);
    try {
      await api.approvePlan(projectId, plan.plan_id, plan.digest, plan.steps.map((step) => step.step_id));
      setApproved(true);
      const started = await api.executePlan(projectId, plan.plan_id);
      setJob(await api.jobStatus(projectId, started.job_id));
    } catch (caught) {
      setError(caught instanceof Error ? caught.message : "The safe fixes did not start.");
    } finally { setBusy(false); }
  }

  if (!project) return <p className="slate text-paper-400" role="status">Loading</p>;
  const plan = run?.plan;
  if (!plan) {
    return <><ProjectRail project={project} /><p className="text-paper-300">There is no check to fix yet. Run preflight first.</p></>;
  }

  const outstanding = [...plan.blocked, ...plan.unresolved];
  const needsDecision = plan.needs_your_decision;
  const destinationName = run?.destinations[0]
    ? names[run.destinations[0].destination_id] ?? run.destinations[0].destination_id
    : "your destination";
  const finished = job?.state === "SUCCEEDED";

  return (
    <>
      <ProjectRail project={project} />
      <div className="mb-8">
        <h2 className="font-display text-2xl text-paper-000">Make the fixes that are safe to automate.</h2>
        <p className="mt-3 max-w-measure text-[15px] leading-relaxed text-paper-300">
          Preflight keeps your original film untouched. It will make only the
          deterministic fixes below, then check the new package again.
        </p>
      </div>

      {job ? (
        <Processing job={job} steps={plan.steps} projectId={projectId} destinationName={destinationName} remainingCount={outstanding.length + needsDecision.length} finished={finished} />
      ) : (
        <>
          {plan.steps.length > 0 && (
            <section className="rounded-[3px] border border-line bg-ink-100 px-6 py-5">
              <h3 className="text-[15px] font-medium text-paper-000">Safe fixes <span className="ml-2 font-normal text-paper-400">{plan.steps.length}</span></h3>
              <p className="mt-1 max-w-measure text-sm leading-relaxed text-paper-400">These changes are deterministic and written to a new copy. Your original stays preserved.</p>
              <ul className="mt-4 space-y-3">{plan.steps.map((step) => <li key={step.step_id}><SafeFixCard step={step} /></li>)}</ul>
              <div className="mt-6 border-t border-line pt-5">
                <button type="button" onClick={applySafeFixes} disabled={busy || approved} className="rounded-[3px] bg-paper-000 px-5 py-2.5 text-sm font-medium text-ink-000 transition hover:bg-white disabled:opacity-50">
                  {busy ? "Starting…" : `Apply ${plan.steps.length} safe fix${plan.steps.length === 1 ? "" : "es"}`}
                </button>
              </div>
            </section>
          )}

          {(outstanding.length > 0 || needsDecision.length > 0) && (
            <section className="mt-8 rounded-[3px] border border-line bg-ink-100 px-6 py-5">
              <h3 className="text-[15px] font-medium text-paper-000">Needs you <span className="ml-2 font-normal text-paper-400">{outstanding.length + needsDecision.length}</span></h3>
              <p className="mt-1 max-w-measure text-sm leading-relaxed text-paper-400">Preflight will not make creative or professional mastering decisions. Each issue below has a next action.</p>
              <ul className="mt-4 space-y-3">
                {outstanding.map((entry, index) => <li key={`${String(entry.destination)}-${String(entry.field)}-${index}`}><NeedsYouCard entry={entry} finding={resolveFinding(entry, run, rules, names)} projectId={projectId} /></li>)}
                {needsDecision.map((step) => <li key={step.step_id}><NeedsYouStepCard step={step} run={run} rules={rules} names={names} projectId={projectId} /></li>)}
              </ul>
            </section>
          )}

          {(plan.steps.length > 0 || outstanding.length > 0 || needsDecision.length > 0) && (
            <details className="mt-8 rounded-[3px] border border-line bg-ink-100 px-6 py-4">
              <summary className="cursor-pointer text-sm text-paper-200 hover:text-paper-000">Technical details</summary>
              <div className="mt-4 space-y-5 text-xs text-paper-400">
                <p className="break-all font-mono">Plan {plan.plan_id ?? "not assigned"} · digest {plan.digest}</p>
                {plan.steps.map((step) => <TechnicalStep key={step.step_id} step={step} />)}
                {needsDecision.map((step) => <TechnicalStep key={step.step_id} step={step} />)}
                {outstanding.length > 0 && <dl className="space-y-1.5 border-l border-line pl-4">{outstanding.map((entry, index) => <div key={index}><dt className="inline">Requirement: </dt><dd className="inline font-mono text-paper-200">{String(entry.field ?? "requirement")}</dd><span> · {String(entry.reason ?? "")}</span></div>)}</dl>}
              </div>
            </details>
          )}
        </>
      )}
      {error && <p role="alert" className="mt-6 border-l-2 border-stop bg-stop-bg/40 py-3 pl-4 text-paper-100">{error}</p>}
    </>
  );
}

function SafeFixCard({ step }: { step: PlanStep }) {
  return <div className="rounded-[3px] bg-ink-000/45 px-4 py-3.5"><h4 className="text-sm font-medium text-paper-000">{operationLabel(step.operation)}</h4><p className="mt-1.5 max-w-measure text-sm leading-relaxed text-paper-200">{step.what_it_does}</p></div>;
}

function TechnicalStep({ step }: { step: PlanStep }) {
  return <div className="border-l border-line pl-4"><p className="font-mono text-paper-200">{step.step_id} · {step.operation}</p><dl className="mt-1 grid gap-x-8 gap-y-1 sm:grid-cols-2"><Detail label="Reads" value={step.input_asset ?? "none"} /><Detail label="Writes" value={step.output} />{Object.entries(step.parameters).map(([key, value]) => <Detail key={key} label={key} value={String(value)} />)}</dl></div>;
}

function Detail({ label, value }: { label: string; value: string }) {
  return <div><span>{label}: </span><span className="font-mono text-paper-200">{value}</span></div>;
}

function resolveFinding(entry: PlanEntry, run: PreflightRun, rules: Rule[], names: Record<string, string>): Finding {
  const destinationId = String(entry.destination ?? "");
  const rawField = String(entry.field ?? "requirement");
  const dot = rawField.indexOf(".");
  const assetType = dot > 0 ? rawField.slice(0, dot) : "master";
  const field = dot > 0 ? rawField.slice(dot + 1) : rawField;
  const matrix = run.destinations.find((item) => item.destination_id === destinationId);
  const assertion = matrix?.assertions.find((item) => `${item.asset_type}.${item.field}` === rawField);
  const rule = assertion ? rules.find((item) => item.rule_id === assertion.rule_id) : undefined;
  return { assertion, rule, destination: names[destinationId] ?? destinationId, assetType, field };
}

function NeedsYouCard({ entry, finding, projectId }: { entry: PlanEntry; finding: Finding; projectId: string }) {
  const { assertion, rule, destination, assetType, field } = finding;
  const action = requirementAction(assetType, field, projectId);
  const expected = rule?.expected ?? assertion?.published ?? "the published requirement";
  const measured = assertion?.measured;
  const requirement = assertion && rule
    ? requirementSentence(destination, assetType, field, rule.operator, expected)
    : `${destination} requires ${fieldLabel(assetType, field).toLowerCase()}.`;
  const current = measured === null || measured === undefined || measured === ""
    ? "Preflight could not measure this on the files supplied."
    : `Your file currently has ${formatValue(measured, field)}.`;
  const preciseAction = userAction(assetType, field, expected, action.instruction);
  return <div className="rounded-[3px] bg-ink-000/45 px-4 py-4">
    <h4 className="text-sm font-medium text-paper-000">{fieldLabel(assetType, field)}</h4>
    <p className="mt-1.5 max-w-measure text-sm leading-relaxed text-paper-200">{requirement} {current}</p>
    <div className="mt-3 grid gap-3 sm:grid-cols-2">
      <div><h5 className="text-xs uppercase tracking-wide text-paper-500">Why Preflight won’t change it</h5><p className="mt-1 text-sm leading-relaxed text-paper-300">{assertion?.explanation ?? String(entry.reason ?? whatYouCanDo(assetType, field))}</p></div>
      <div><h5 className="text-xs uppercase tracking-wide text-paper-500">What you need to do</h5><p className="mt-1 text-sm leading-relaxed text-paper-200">{preciseAction}</p><Link href={action.href} className="mt-3 inline-flex rounded-[3px] border border-line-strong px-3.5 py-2 text-sm text-paper-100 transition hover:bg-ink-200">{action.label}</Link></div>
    </div>
  </div>;
}

function NeedsYouStepCard({
  step,
  run,
  rules,
  names,
  projectId,
}: {
  step: PlanStep;
  run: PreflightRun;
  rules: Rule[];
  names: Record<string, string>;
  projectId: string;
}) {
  const rule = rules.find((item) => step.resolves.includes(item.rule_id));
  const destinationId = rule?.destination ?? run.destinations[0]?.destination_id ?? "";
  const destination = names[destinationId] ?? destinationId;
  const assetType = rule?.asset_type ?? "video";
  const field = rule?.field ?? "codec";
  const expected = rule?.expected ?? "the published requirement";
  const action = requirementAction(assetType, field, projectId);
  const requirement = rule
    ? requirementSentence(destination, assetType, field, rule.operator, expected)
    : "This destination requires a version of the film that needs your decision.";
  return <div className="rounded-[3px] bg-ink-000/45 px-4 py-4">
    <h4 className="text-sm font-medium text-paper-000">{fieldLabel(assetType, field)}</h4>
    <p className="mt-1.5 max-w-measure text-sm leading-relaxed text-paper-200">{requirement}</p>
    <div className="mt-3 grid gap-3 sm:grid-cols-2">
      <div><h5 className="text-xs uppercase tracking-wide text-paper-500">Why Preflight won’t change it</h5><p className="mt-1 text-sm leading-relaxed text-paper-300">{rule ? whatYouCanDo(assetType, field) : step.what_it_does}</p></div>
      <div><h5 className="text-xs uppercase tracking-wide text-paper-500">What you need to do</h5><p className="mt-1 text-sm leading-relaxed text-paper-200">{userAction(assetType, field, expected, action.instruction)}</p><Link href={action.href} className="mt-3 inline-flex rounded-[3px] border border-line-strong px-3.5 py-2 text-sm text-paper-100 transition hover:bg-ink-200">{action.label}</Link></div>
    </div>
  </div>;
}

function userAction(assetType: string, field: string, expected: unknown, fallback: string): string {
  const value = formatValue(expected, field);
  if (assetType === "video" && ["codec", "profile", "container", "bitrateBps", "widthPx", "heightPx", "frameRate"].includes(field)) return `Export a version with ${value} in your editing or mastering software, then replace the film in Preflight.`;
  if (assetType === "audio" && field === "channels") return `Provide a ${value} mix, then replace the film in Preflight.`;
  if (assetType === "audio") return `Export a version with ${value} from your editing or mastering software, then replace the film in Preflight.`;
  return fallback;
}

function Processing({ job, steps, projectId, destinationName, remainingCount, finished }: { job: JobStatus; steps: PlanStep[]; projectId: string; destinationName: string; remainingCount: number; finished: boolean }) {
  const failed = job.state === "FAILED" || job.state === "CANCELLED";
  return <section className="rounded-[3px] border border-line bg-ink-100 p-6">
    <div className="flex flex-wrap items-baseline justify-between gap-3"><h3 className="font-display text-lg text-paper-000">{finished ? `${steps.length} safe fix${steps.length === 1 ? "" : "es"} completed` : failed ? "Processing stopped" : "Applying safe fixes"}</h3><StatusChip tone={finished ? "ok" : failed ? "stop" : "think"}>{job.state.toLowerCase()}</StatusChip></div>
    <p className="mt-3 max-w-measure text-sm leading-relaxed text-paper-300">{finished ? `Your ${destinationName} package has been checked again from the files Preflight produced.` : job.message}</p>
    {!finished && !failed && <Working label="Applying the safe fixes to a copy of your film" />}
    {finished && <><p className="mt-5 max-w-measure text-sm leading-relaxed text-paper-200">Your {destinationName} delivery is still not ready. {remainingCount} issue{remainingCount === 1 ? " needs" : "s need"} you.</p><Link href={`/projects/${projectId}/packages`} className="mt-5 inline-flex rounded-[3px] bg-paper-000 px-5 py-2.5 text-sm font-medium text-ink-000 transition hover:bg-white">Resolve remaining issues</Link></>}
    {failed && <p className="mt-4 border-l-2 border-stop bg-stop-bg/30 py-3 pl-4 text-sm text-paper-100">Your original files are untouched. Nothing was marked ready.</p>}
  </section>;
}
