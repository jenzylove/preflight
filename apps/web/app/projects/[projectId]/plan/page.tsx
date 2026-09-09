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
type FindingSource = { finding: Finding; entry?: PlanEntry; step?: PlanStep };
type UserTask = {
  key: string;
  label: string;
  summary: string;
  href: string;
  buttonLabel: string;
  why: string;
  sources: FindingSource[];
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
    load().catch((caught) => setError(caught instanceof Error ? caught.message : "Could not load the plan."));
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
      await api.approvePlan(projectId, plan.plan_id, plan.digest, safeFixes.flatMap((fix) => fix.steps.map((step) => step.step_id)));
      setApproved(true);
      const started = await api.executePlan(projectId, plan.plan_id);
      setJob(await api.jobStatus(projectId, started.job_id));
    } catch (caught) {
      setError(caught instanceof Error ? caught.message : "The safe fixes did not start.");
    } finally { setBusy(false); }
  }

  if (!project) return <p className="slate text-paper-400" role="status">Loading</p>;
  const plan = run?.plan;
  if (!plan) return <><ProjectRail project={project} /><p className="text-paper-300">There is no check to fix yet. Run preflight first.</p></>;

  const tasks = buildTasks(plan, run!, rules, names, projectId);
  const safeFixes = buildSafeFixes(plan, run!, rules, names);
  const finished = job?.state === "SUCCEEDED";

  return (
    <>
      <ProjectRail project={project} />
      <div className="mb-8">
        <h2 className="font-display text-2xl text-paper-000">Make the fixes that are safe to automate.</h2>
        <p className="mt-3 max-w-measure text-[15px] leading-relaxed text-paper-300">Preflight keeps your original film untouched. It will make only the deterministic fixes below, then check the new package again.</p>
      </div>

      {job ? (
        <Processing job={job} steps={plan.steps} projectId={projectId} finished={finished} />
      ) : (
        <>
          {safeFixes.length > 0 && (
            <section className="rounded-[3px] border border-line bg-ink-100 px-6 py-5">
              <h3 className="text-[15px] font-medium text-paper-000">Preflight can fix <span className="ml-2 font-normal text-paper-400">{safeFixes.length}</span></h3>
              <ul className="mt-4 space-y-2">{safeFixes.map((fix) => <li key={fix.key}><SafeFixRow fix={fix} /></li>)}</ul>
              <div className="mt-6 border-t border-line pt-5">
                <button type="button" onClick={applySafeFixes} disabled={busy || approved} className="rounded-[3px] bg-paper-000 px-5 py-2.5 text-sm font-medium text-ink-000 transition hover:bg-white disabled:opacity-50">
                  {busy ? "Starting…" : `Apply ${safeFixes.length} safe fix${safeFixes.length === 1 ? "" : "es"}`}
                </button>
              </div>
            </section>
          )}

          {tasks.length > 0 && (
            <section className="mt-8 rounded-[3px] border border-line bg-ink-100 px-6 py-5">
              <h3 className="text-[15px] font-medium text-paper-000">You need to do <span className="ml-2 font-normal text-paper-400">{tasks.length}</span></h3>
              <ul className="mt-4 space-y-3">{tasks.map((task) => <li key={task.key}><UserTaskCard task={task} /></li>)}</ul>
            </section>
          )}

          {(safeFixes.length > 0 || tasks.length > 0) && <TechnicalDetails plan={plan} tasks={tasks} />}
        </>
      )}
      {error && <p role="alert" className="mt-6 border-l-2 border-stop bg-stop-bg/40 py-3 pl-4 text-paper-100">{error}</p>}
    </>
  );
}

type SafeFix = { key: string; label: string; summary: string; steps: PlanStep[] };

function buildSafeFixes(plan: Plan, run: PreflightRun, rules: Rule[], names: Record<string, string>): SafeFix[] {
  const grouped = new Map<string, SafeFix>();
  for (const step of plan.steps) {
    const first = findingForRule(step.resolves[0], run, rules, names);
    const stepFindings = step.resolves.map((ruleId) => findingForRule(ruleId, run, rules, names)).filter((finding): finding is Finding => Boolean(finding));
    if (stepFindings.some(isMisreadFilename)) continue;
    const key = step.operation;
    const current = grouped.get(key);
    if (current) { current.steps.push(step); continue; }
    const destination = first?.destination ?? "the destination";
    const label = safeFixLabel(step.operation);
    const summary = step.operation === "normalise_loudness"
      ? `Outside ${destination}’s range → Preflight will correct it`
      : step.operation === "rewrite_container_metadata"
        ? "Needs updating → Preflight will correct it"
        : `${fieldLabel(first?.assetType ?? "file", first?.field ?? "property")} needs updating → Preflight will correct it`;
    grouped.set(key, { key, label, summary, steps: [step] });
  }
  return [...grouped.values()];
}

function safeFixLabel(operation: string): string {
  if (operation === "normalise_loudness") return "Audio loudness";
  if (operation === "rewrite_container_metadata") return "Delivery metadata";
  return operationLabel(operation);
}

function SafeFixRow({ fix }: { fix: SafeFix }) {
  return <div className="rounded-[3px] bg-ink-000/45 px-4 py-3"><h4 className="text-sm font-medium text-paper-000">{fix.label}</h4><p className="mt-1 text-sm text-paper-300">{fix.summary}</p></div>;
}

function buildTasks(plan: Plan, run: PreflightRun, rules: Rule[], names: Record<string, string>, projectId: string): UserTask[] {
  const grouped = new Map<string, FindingSource[]>();
  const add = (source: FindingSource) => {
    const key = taskKey(source.finding);
    grouped.set(key, [...(grouped.get(key) ?? []), source]);
  };
  for (const entry of [...plan.blocked, ...plan.unresolved]) add({ entry, finding: resolveFinding(entry, run, rules, names) });
  for (const step of plan.needs_your_decision) {
    for (const ruleId of step.resolves) add({ step, finding: findingForRule(ruleId, run, rules, names) ?? fallbackFinding(step, names) });
  }
  for (const step of plan.steps) {
    const findings = step.resolves.map((ruleId) => findingForRule(ruleId, run, rules, names)).filter((finding): finding is Finding => Boolean(finding));
    if (findings.some(isMisreadFilename)) {
      for (const finding of findings.filter(isMisreadFilename)) add({ step, finding });
    }
  }
  return [...grouped.entries()].map(([key, sources]) => makeTask(key, sources, projectId));
}

function taskKey(finding: Finding): string {
  if (isMisreadFilename(finding)) return `review:${finding.rule?.rule_id ?? "filename"}`;
  if (finding.assetType === "subtitle" && finding.field === "burnedIn") return "burned-in-subtitles";
  if (finding.assetType === "subtitle") return "subtitle-file";
  if (finding.assetType === "audio" && finding.field === "channels") return "audio-mix";
  if (finding.assetType === "audio") return "audio-export";
  if (finding.assetType === "video") return "video-export";
  if (finding.assetType === "poster") return "poster-file";
  if (finding.assetType === "metadata" || finding.assetType === "package") return "delivery-details";
  return `${finding.assetType}:${finding.field}`;
}

function makeTask(key: string, sources: FindingSource[], projectId: string): UserTask {
  const firstSource = sources[0];
  if (!firstSource) throw new Error("Cannot render an empty user action.");
  const first = firstSource.finding;
  const suspicious = isMisreadFilename(first);
  const action = suspicious ? null : requirementAction(first.assetType, first.field, projectId);
  const label = suspicious ? "Review filename requirement" : taskLabel(key, action?.label ?? "Resolve requirement");
  const href = suspicious ? `/projects/${projectId}/preflight#rule-${first.rule?.rule_id ?? ""}` : action!.href;
  const buttonLabel = suspicious ? "Review requirement" : action!.label;
  return {
    key,
    label,
    summary: taskSummary(key, sources),
    href,
    buttonLabel,
    why: suspicious
      ? "The extracted rule says ISDCF is a filename pattern, but the source identifies ISDCF as a naming convention. Check the source and set this rule aside with a reason if it was misread."
      : first.assertion?.explanation ?? String(firstSource.entry?.reason ?? whatYouCanDo(first.assetType, first.field)),
    sources,
  };
}

function taskLabel(key: string, fallback: string): string {
  if (key === "subtitle-file") return "Add subtitle file";
  if (key === "audio-mix") return "Replace the audio mix";
  if (key === "video-export") return "Export the required video version";
  if (key === "burned-in-subtitles") return "Add burned-in subtitles";
  return fallback;
}

function taskSummary(key: string, sources: FindingSource[]): string {
  const firstSource = sources[0];
  if (!firstSource) return "This requirement needs your attention.";
  const first = firstSource.finding;
  const destination = first.destination;
  const values = sources.map(({ finding }) => finding.rule?.expected ?? finding.assertion?.published ?? "the published requirement");
  const expected = unique(values.map((value) => formatValue(value, first.field))).join(" or ");
  const measured = first.assertion?.measured;
  if (key === "subtitle-file") return `No separate subtitle file was provided. ${destination} requires ${expected}.`;
  if (key === "audio-mix") return `Your film is ${formatValue(measured, first.field)}. ${destination} requires ${expected}.`;
  if (key === "video-export") return `Your film is ${formatValue(measured, first.field)}. ${destination} requires ${expected}.`;
  if (key === "burned-in-subtitles") return `${destination} requires subtitles to be visible in the picture itself.`;
  if (key.startsWith("review:")) return "The source may describe a naming convention, not a filename pattern.";
  return `${requirementSentence(destination, first.assetType, first.field, first.rule?.operator ?? "eq", first.rule?.expected ?? first.assertion?.published ?? "required")} ${measured == null ? "Preflight could not measure this on the files supplied." : `Your file currently has ${formatValue(measured, first.field)}.`}`;
}

function UserTaskCard({ task }: { task: UserTask }) {
  return <div className="rounded-[3px] bg-ink-000/45 px-4 py-4"><div className="flex flex-wrap items-baseline justify-between gap-3"><h4 className="text-sm font-medium text-paper-000">{task.label}</h4><Link href={task.href} className="rounded-[3px] border border-line-strong px-3.5 py-2 text-sm text-paper-100 transition hover:bg-ink-200">{task.buttonLabel}</Link></div><p className="mt-2 max-w-measure text-sm leading-relaxed text-paper-200">{task.summary}</p><details className="mt-3"><summary className="cursor-pointer text-xs text-paper-400 hover:text-paper-200">Why Preflight won’t do this automatically</summary><p className="mt-2 max-w-measure text-sm leading-relaxed text-paper-300">{task.why}</p></details></div>;
}

function TechnicalDetails({ plan, tasks }: { plan: Plan; tasks: UserTask[] }) {
  return <details className="mt-8 rounded-[3px] border border-line bg-ink-100 px-6 py-4"><summary className="cursor-pointer text-sm text-paper-200 hover:text-paper-000">Technical details</summary><div className="mt-4 space-y-5 text-xs text-paper-400"><p className="break-all font-mono">Plan {plan.plan_id ?? "not assigned"} · digest {plan.digest}</p>{[...plan.steps, ...plan.needs_your_decision].map((step) => <div key={step.step_id} className="border-l border-line pl-4"><p className="font-mono text-paper-200">{step.step_id} · {step.operation}</p><p className="mt-1">Reads: <span className="font-mono text-paper-200">{step.input_asset}</span> · Writes: <span className="font-mono text-paper-200">{step.output}</span></p><p className="mt-1 font-mono">{Object.entries(step.parameters).map(([key, value]) => `${key}=${String(value)}`).join(" · ")}</p></div>)}{tasks.map((task) => <div key={task.key} className="border-t border-line pt-3"><p className="text-paper-300">{task.label}</p><ul className="mt-1 space-y-1">{task.sources.map((source, index) => <li key={index}><span className="font-mono text-paper-200">{source.finding.assetType}.{source.finding.field}</span> · {source.finding.assertion?.result ?? String(source.entry?.needs ?? "unresolved")} · {source.finding.assertion?.published ?? String(source.entry?.published ?? "")}{source.finding.rule?.source_excerpt ? <span> · {source.finding.rule.source_excerpt}</span> : null}{source.finding.rule?.source_url ? <span> · <a href={source.finding.rule.source_url} target="_blank" rel="noreferrer" className="text-paper-200 underline">source</a></span> : null}</li>)}</ul></div>)}</div></details>;
}

function findingForRule(ruleId: string | undefined, run: PreflightRun, rules: Rule[], names: Record<string, string>): Finding | undefined {
  if (!ruleId) return undefined;
  const rule = rules.find((item) => item.rule_id === ruleId);
  if (!rule) return undefined;
  const matrix = run.destinations.find((item) => item.destination_id === rule.destination);
  const assertion = matrix?.assertions.find((item) => item.rule_id === ruleId);
  return { assertion, rule, destination: names[rule.destination] ?? rule.destination, assetType: rule.asset_type, field: rule.field };
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

function fallbackFinding(step: PlanStep, names: Record<string, string>): Finding {
  return { destination: names["sundance"] ?? "the destination", assetType: step.operation === "translate_subtitles" ? "subtitle" : "video", field: step.operation === "translate_subtitles" ? "language" : "codec" };
}

function isMisreadFilename(finding: Finding): boolean {
  return finding.assetType === "package" && finding.field === "fileNamePattern" && finding.rule?.operator === "eq" && String(finding.rule.expected ?? finding.assertion?.published ?? "").toLowerCase().includes("isdcf");
}

function unique(values: string[]): string[] {
  return [...new Set(values.filter(Boolean))];
}

function Processing({ job, steps, projectId, finished }: { job: JobStatus; steps: PlanStep[]; projectId: string; finished: boolean }) {
  const failed = job.state === "FAILED" || job.state === "CANCELLED";
  return <section className="rounded-[3px] border border-line bg-ink-100 p-6"><div className="flex flex-wrap items-baseline justify-between gap-3"><h3 className="font-display text-lg text-paper-000">{finished ? `${steps.length} safe fix${steps.length === 1 ? "" : "es"} completed` : failed ? "Processing stopped" : "Applying safe fixes"}</h3><StatusChip tone={finished ? "ok" : failed ? "stop" : "think"}>{job.state.toLowerCase()}</StatusChip></div><p className="mt-3 max-w-measure text-sm leading-relaxed text-paper-300">{finished ? "Safe fixes completed. Preflight rechecked the new files." : job.message}</p>{!finished && !failed && <Working label="Applying the safe fixes to a copy of your film" />}{finished && <Link href={`/projects/${projectId}/packages`} className="mt-5 inline-flex rounded-[3px] bg-paper-000 px-5 py-2.5 text-sm font-medium text-ink-000 transition hover:bg-white">See recheck result</Link>}{failed && <p className="mt-4 border-l-2 border-stop bg-stop-bg/30 py-3 pl-4 text-sm text-paper-100">Your original files are untouched. Nothing was marked ready.</p>}</section>;
}
