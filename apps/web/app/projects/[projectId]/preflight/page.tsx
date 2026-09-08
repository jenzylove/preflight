"use client";

import Link from "next/link";
import { use, useCallback, useEffect, useState } from "react";

import { StatusChip, Working } from "@/components/Status";
import { ProjectRail } from "@/components/workspace/Rail";
import { Workspace } from "@/components/workspace/Workspace";
import { api } from "@/lib/api";
import { fieldLabel, formatValue, requirementSentence } from "@/lib/language";
import type {
  Assertion,
  Conflict,
  DestinationMatrix,
  PreflightRun,
  Project,
  Rule,
} from "@/lib/types";

/**
 * What each destination requires, beside what the film actually is.
 *
 * The two numbers stay side by side and never collapse into a score. A single
 * percentage would be easier to read and would hide the only thing that
 * matters: which requirement, from which source, measured how.
 *
 * Conflicts sit above everything, because a requirement two destinations
 * disagree about is not a property of the film and cannot be fixed by
 * changing it.
 */
export default function PreflightPage({
  params,
}: {
  params: Promise<{ projectId: string }>;
}) {
  const { projectId } = use(params);
  return (
    <Workspace wide>
      <Preflight projectId={projectId} />
    </Workspace>
  );
}

function Preflight({ projectId }: { projectId: string }) {
  const [project, setProject] = useState<Project | null>(null);
  const [run, setRun] = useState<PreflightRun | null>(null);
  const [rules, setRules] = useState<Rule[]>([]);
  // Matrices are keyed by slug. Nobody sent their film to
  // "sundance-film-festival"; they sent it to Sundance Film Festival.
  const [names, setNames] = useState<Record<string, string>>({});
  const [running, setRunning] = useState(false);
  const [error, setError] = useState<string | null>(null);

  const load = useCallback(async () => {
    const p = await api.getProject(projectId);
    setProject(p);
    const [latest, ruleList] = await Promise.all([
      api.latestPreflight(projectId).catch(() => null),
      api.listRules(projectId).catch(() => [] as Rule[]),
    ]);
    setRun(latest);
    setRules(ruleList);
    const destinations = await api.listDestinations().catch(() => []);
    setNames(Object.fromEntries(destinations.map((d) => [d.slug, d.name])));
  }, [projectId]);

  useEffect(() => {
    load().catch((caught) =>
      setError(caught instanceof Error ? caught.message : "Could not load this project."),
    );
  }, [load]);

  async function runPreflight() {
    setRunning(true);
    setError(null);
    try {
      setRun(await api.runPreflight(projectId));
      setRules(await api.listRules(projectId).catch(() => rules));
    } catch (caught) {
      setError(caught instanceof Error ? caught.message : "Preflight did not complete.");
    } finally {
      setRunning(false);
    }
  }

  if (!project) {
    return <p className="slate text-paper-400" role="status">Loading</p>;
  }

  return (
    <>
      <ProjectRail project={project} />

      <div className="mb-8 flex flex-wrap items-end justify-between gap-4">
        <div>
          <h2 className="font-display text-2xl text-paper-000">
            What each destination requires
          </h2>
          <p className="mt-3 max-w-measure text-[15px] leading-relaxed text-paper-300">
            Every requirement below was retrieved from the destination&rsquo;s own
            published documentation. Every measurement was taken from your files
            by ffprobe, ffmpeg and Pillow. Nothing here is inferred.
          </p>
        </div>
        <button
          type="button"
          onClick={runPreflight}
          disabled={running}
          className="rounded-[3px] border border-line-strong px-4 py-2 text-sm
                     text-paper-100 transition hover:bg-ink-200 disabled:opacity-50"
        >
          {run ? "Run again" : "Run preflight"}
        </button>
      </div>

      {running && <Working label="Comparing your files against current requirements" />}

      {error && (
        <p role="alert" className="border-l-2 border-stop bg-stop-bg/40 py-3 pl-4 text-paper-100">
          {error}
        </p>
      )}

      {!run && !running && !error && (
        <p className="text-paper-300">
          No preflight has run for this project yet.
        </p>
      )}

      {run && (
        <>
          {run.conflicts.length > 0 && (
            <section className="mb-10">
              <h3 className="slate mb-3 text-paper-400">Before anything else</h3>
              <div className="space-y-3">
                {run.conflicts.map((conflict, index) => (
                  <ConflictCard key={index} conflict={conflict} />
                ))}
              </div>
            </section>
          )}

          <div className="space-y-8">
            {run.destinations.map((matrix) => (
              <Matrix
                key={matrix.destination_id}
                displayName={names[matrix.destination_id] ?? matrix.destination_id}
                matrix={matrix}
                rules={rules}
                projectId={projectId}
                onChanged={load}
              />
            ))}
          </div>

          <details className="mt-6">
            <summary className="cursor-pointer text-xs text-paper-400 transition hover:text-paper-200">
              Technical details of this check
            </summary>
            <p className="mt-2 font-mono text-xs text-paper-500">
              comparison digest {run.comparison_digest}
            </p>
            {run.destinations.map((m) => (
              <p key={m.destination_id} className="mt-1 font-mono text-xs text-paper-500">
                {m.destination_id} rule pack {m.rule_pack_digest}
              </p>
            ))}
          </details>

          {run.plan?.plan_id && (
            <div className="mt-10 flex justify-end">
              <Link
                href={`/projects/${projectId}/plan`}
                className="rounded-[3px] bg-paper-000 px-5 py-2.5 text-sm font-medium
                           text-ink-000 transition hover:bg-white"
              >
                Review the repair plan
              </Link>
            </div>
          )}

          <p className="mt-10 border-t border-line pt-6 text-sm text-paper-400">
            Preflight checks your files against what each destination publishes.
            It cannot promise that a festival or platform will accept your
            delivery.
          </p>
        </>
      )}
    </>
  );
}

function ConflictCard({ conflict }: { conflict: Conflict }) {
  const hard = conflict.strength === "hard";
  const occurrences = conflict.occurrences ?? 1;

  return (
    <div
      className={`rounded-[3px] border-l-2 p-5 ${
        hard ? "border-stop bg-stop-bg/30" : "border-review bg-review-bg/25"
      }`}
    >
      <div className="flex flex-wrap items-baseline justify-between gap-3">
        <h4 className="text-[15px] font-medium text-paper-000">
          {hard
            ? "These destinations require different deliveries"
            : "These destinations prefer different deliveries"}
        </h4>
        <span className="font-mono text-xs text-paper-400">
          {conflict.assetType}.{conflict.field}
        </span>
      </div>

      <ul className="mt-4 space-y-2.5">
        {conflict.destinations.map((destination, i) => (
          <li key={destination} className="text-sm">
            <span className="text-paper-000">{destination}</span>
            <span className="text-paper-300"> requires </span>
            <span className="font-mono text-paper-100">
              {conflict.requirements[i]}
            </span>
          </li>
        ))}
      </ul>

      <p className="mt-4 text-sm text-paper-300">
        {hard
          ? "No single file satisfies both. Preflight will build a separate package for each."
          : "One file can go to both, but one destination gets a result it does not recommend."}
      </p>

      {occurrences > 1 && (
        <p className="mt-2 text-xs text-paper-400">
          Stated {occurrences} times across the retrieved sources.
        </p>
      )}
    </div>
  );
}

/**
 * One destination's verdict.
 *
 * The old version of this opened with a rule pack digest and a chip reading
 * "42 outstanding", where the 42 counted context and recommended rules that
 * could not block anything. It was frightening and it was wrong.
 *
 * So the first line answers the only question that matters — is my film ready
 * for this place — and the findings underneath are grouped by what the person
 * has to do about them, in that order: what only they can decide, what
 * Preflight will fix for them, what it still needs, and what already passed.
 */
function Matrix({
  matrix,
  displayName,
  rules,
  projectId,
  onChanged,
}: {
  matrix: DestinationMatrix;
  displayName: string;
  rules: Rule[];
  projectId: string;
  onChanged: () => Promise<void>;
}) {
  const [showPassed, setShowPassed] = useState(false);

  // Only a required rule can stop a delivery. Recommended and context rules are
  // real and are kept, but they are advice, and counting them as problems is
  // what produced a number nobody could act on.
  const binding = matrix.assertions.filter((a) => a.severity === "required");
  const advisory = matrix.assertions.filter((a) => a.severity !== "required");

  const passed = binding.filter((a) => a.result === "PASS");
  const needsDecision = binding.filter(
    (a) => a.result === "REVIEW_REQUIRED" || a.result === "UNSUPPORTED",
  );
  const canFix = binding.filter((a) => a.result === "REPAIRABLE");
  const needInfo = binding.filter(
    (a) => a.result === "NOT_MEASURED" || a.result === "AMBIGUOUS",
  );

  const name = displayName;
  const blocked = needsDecision.length + canFix.length + needInfo.length;

  return (
    <section className="rounded-[3px] border border-line bg-ink-100">
      <header className="border-b border-line px-6 py-5">
        <h3 className="font-display text-xl leading-snug text-paper-000">
          {matrix.ready
            ? `Your film meets what ${name} publishes`
            : `Your film is not ready for ${name} yet`}
        </h3>
        <p className="mt-2 text-sm text-paper-300">
          {passed.length} of {binding.length}{" "}
          {binding.length === 1 ? "check" : "checks"} passed
          {blocked > 0 && (
            <>
              {" · "}
              {blocked} still to resolve
            </>
          )}
        </p>
      </header>

      <div className="divide-y divide-line">
        <Group
          title="Needs your decision"
          blurb="Fixing these would change the picture, the timing or the meaning of your film, so Preflight will not do it on its own."
          tone="decide"
          assertions={needsDecision}
          rules={rules}
          projectId={projectId}
          destination={name}
          onChanged={onChanged}
        />
        <Group
          title="Preflight can fix these safely"
          blurb="Deterministic changes that never touch your picture. Your original is not modified."
          tone="fix"
          assertions={canFix}
          rules={rules}
          projectId={projectId}
          destination={name}
          onChanged={onChanged}
        />
        <Group
          title="Information Preflight still needs"
          blurb="Either the file to check was not supplied, or this destination states the requirement in a way that cannot be measured."
          tone="info"
          assertions={needInfo}
          rules={rules}
          projectId={projectId}
          destination={name}
          onChanged={onChanged}
        />

        {advisory.length > 0 && (
          <Group
            title="Recommendations"
            blurb="Not required. These will not stop your delivery."
            tone="info"
            assertions={advisory.filter((a) => a.result !== "PASS")}
            rules={rules}
            projectId={projectId}
            destination={name}
            onChanged={onChanged}
          />
        )}

        {passed.length > 0 && (
          <div className="px-6 py-4">
            <button
              type="button"
              onClick={() => setShowPassed((v) => !v)}
              aria-expanded={showPassed}
              className="text-sm text-paper-300 transition hover:text-paper-000"
            >
              {showPassed ? "Hide" : "Show"} the {passed.length} checks that passed
            </button>
            {showPassed && (
              <ul className="mt-4 space-y-3">
                {passed.map((assertion) => (
                  <Finding
                    key={`${assertion.destination_id}-${assertion.rule_id}`}
                    assertion={assertion}
                    rule={rules.find((r) => r.rule_id === assertion.rule_id)}
                    projectId={projectId}
                    destination={name}
                    onChanged={onChanged}
                  />
                ))}
              </ul>
            )}
          </div>
        )}
      </div>
    </section>
  );
}

function Group({
  title,
  blurb,
  tone,
  assertions,
  rules,
  projectId,
  destination,
  onChanged,
}: {
  title: string;
  blurb: string;
  tone: "decide" | "fix" | "info";
  assertions: Assertion[];
  rules: Rule[];
  projectId: string;
  destination: string;
  onChanged: () => Promise<void>;
}) {
  if (assertions.length === 0) return null;

  const border =
    tone === "decide"
      ? "border-review"
      : tone === "fix"
        ? "border-go"
        : "border-line-strong";

  return (
    <div className="px-6 py-5">
      <div className={`border-l-2 pl-4 ${border}`}>
        <h4 className="text-[15px] font-medium text-paper-000">
          {title}
          <span className="ml-2 text-sm font-normal text-paper-400">
            {assertions.length}
          </span>
        </h4>
        <p className="mt-1 max-w-measure text-sm leading-relaxed text-paper-400">
          {blurb}
        </p>
      </div>

      <ul className="mt-4 space-y-3">
        {assertions.map((assertion) => (
          <Finding
            key={`${assertion.destination_id}-${assertion.rule_id}`}
            assertion={assertion}
            rule={rules.find((r) => r.rule_id === assertion.rule_id)}
            projectId={projectId}
            destination={destination}
            onChanged={onChanged}
          />
        ))}
      </ul>
    </div>
  );
}

/**
 * One finding, as a sentence.
 *
 * "Published: eq jpeg2000 / Your file: h264" is a comparison a machine made.
 * "Berlinale asks for video format to be JPEG 2000. Your film is H.264." is
 * the same fact in a form somebody can act on. The operator, the exact value,
 * the rule identity and the quoted source are all still one disclosure away,
 * because that evidence is the reason to believe any of this.
 */
function Finding({
  assertion,
  rule,
  projectId,
  destination,
  onChanged,
}: {
  assertion: Assertion;
  rule?: Rule;
  projectId: string;
  destination: string;
  onChanged: () => Promise<void>;
}) {
  const [open, setOpen] = useState(false);
  const setAside = rule?.disposition === "set_aside";
  const label = fieldLabel(assertion.asset_type, assertion.field);

  const measured =
    assertion.measured === null || assertion.measured === ""
      ? null
      : formatValue(assertion.measured, assertion.field);

  return (
    <li className="rounded-[3px] bg-ink-000/40 px-4 py-3.5">
      <div className="flex flex-wrap items-baseline justify-between gap-3">
        <span className="text-sm font-medium text-paper-000">{label}</span>
        {setAside && <StatusChip tone="idle">You set this aside</StatusChip>}
      </div>

      <p className="mt-1.5 max-w-measure text-sm leading-relaxed text-paper-200">
        {requirementSentence(
          destination,
          assertion.asset_type,
          assertion.field,
          rule?.operator ?? "eq",
          rule?.expected ?? assertion.published,
        )}{" "}
        {measured ? (
          <span className="text-paper-300">Your film is {measured}.</span>
        ) : (
          <span className="text-paper-400">
            Preflight has not measured this on your files.
          </span>
        )}
      </p>

      {assertion.result === "REVIEW_REQUIRED" && (
        <p className="mt-1.5 text-sm text-paper-400">
          Changing this would re-encode the picture, so Preflight will not do it
          automatically.
        </p>
      )}
      {assertion.result === "UNSUPPORTED" && (
        <p className="mt-1.5 text-sm text-paper-400">
          Preflight has no safe operation for this. It needs judgement or
          authority it does not have.
        </p>
      )}
      {assertion.result === "REPAIRABLE" && (
        <p className="mt-1.5 text-sm text-paper-400">
          Preflight can correct this without re-encoding the picture.
        </p>
      )}

      <div className="mt-3 flex flex-wrap items-center gap-4">
        <button
          type="button"
          onClick={() => setOpen((value) => !value)}
          aria-expanded={open}
          className="text-xs text-paper-400 transition hover:text-paper-100"
        >
          {open ? "Hide technical details" : "Technical details"}
        </button>
        {rule && (
          <ReviewRule rule={rule} projectId={projectId} onChanged={onChanged} />
        )}
      </div>

      {open && (
        <div className="mt-3 border-l border-line pl-4">
          <dl className="grid gap-x-8 gap-y-1 text-xs sm:grid-cols-2">
            <div>
              <dt className="inline text-paper-400">Field: </dt>
              <dd className="inline font-mono text-paper-200">
                {assertion.asset_type}.{assertion.field}
              </dd>
            </div>
            <div>
              <dt className="inline text-paper-400">Result: </dt>
              <dd className="inline font-mono text-paper-200">{assertion.result}</dd>
            </div>
            <div>
              <dt className="inline text-paper-400">Published: </dt>
              <dd className="inline font-mono text-paper-200">
                {rule ? `${rule.operator} ` : ""}
                {assertion.published}
              </dd>
            </div>
            <div>
              <dt className="inline text-paper-400">Measured: </dt>
              <dd className="inline font-mono text-paper-200">
                {assertion.measured === null
                  ? "not measured"
                  : String(assertion.measured)}
              </dd>
            </div>
          </dl>

          {assertion.explanation && (
            <p className="mt-2 text-xs text-paper-300">{assertion.explanation}</p>
          )}

          {assertion.source_excerpt && (
            <p className="mt-3 text-xs italic leading-relaxed text-paper-200">
              &ldquo;{assertion.source_excerpt}&rdquo;
            </p>
          )}
          {assertion.source_url && (
            <a
              href={assertion.source_url}
              target="_blank"
              rel="noreferrer noopener"
              className="mt-2 inline-block break-all text-xs text-accent underline underline-offset-4"
            >
              {assertion.source_url}
            </a>
          )}
        </div>
      )}
    </li>
  );
}

function ReviewRule({
  rule,
  projectId,
  onChanged,
}: {
  rule: Rule;
  projectId: string;
  onChanged: () => Promise<void>;
}) {
  const [open, setOpen] = useState(false);
  const [reason, setReason] = useState(rule.disposition_reason ?? "");
  const [busy, setBusy] = useState(false);
  const [failure, setFailure] = useState<string | null>(null);

  async function decide(action: "accept" | "set_aside") {
    setBusy(true);
    setFailure(null);
    try {
      await api.setDisposition(projectId, rule.rule_id, action, reason.trim());
      await onChanged();
      setOpen(false);
    } catch (caught) {
      setFailure(
        caught instanceof Error ? caught.message : "That decision was not recorded.",
      );
    } finally {
      setBusy(false);
    }
  }

  if (!open) {
    return (
      <button
        type="button"
        onClick={() => setOpen(true)}
        className="text-xs text-paper-400 transition hover:text-paper-100"
      >
        {rule.disposition === "set_aside"
          ? "Reconsider this requirement"
          : "Review this requirement"}
      </button>
    );
  }

  return (
    <div className="mt-3 w-full rounded-[3px] border border-line-strong bg-ink-000 p-4">
      <p className="text-sm text-paper-100">
        Preflight may have read this requirement incorrectly. Check the source
        before setting it aside.
      </p>

      <dl className="mt-4 space-y-1.5 text-xs">
        <div className="flex gap-3">
          <dt className="w-24 shrink-0 text-paper-400">Read as</dt>
          <dd className="font-mono text-paper-100">
            {rule.field} {rule.operator} {rule.expected}
          </dd>
        </div>
        <div className="flex gap-3">
          <dt className="w-24 shrink-0 text-paper-400">Confidence</dt>
          <dd className="text-paper-200">{rule.confidence}</dd>
        </div>
        {rule.source_excerpt && (
          <div className="flex gap-3">
            <dt className="w-24 shrink-0 text-paper-400">Source says</dt>
            <dd className="italic text-paper-200">
              &ldquo;{rule.source_excerpt}&rdquo;
            </dd>
          </div>
        )}
        {rule.source_url && (
          <div className="flex gap-3">
            <dt className="w-24 shrink-0 text-paper-400">Published at</dt>
            <dd>
              <a
                href={rule.source_url}
                target="_blank"
                rel="noreferrer noopener"
                className="break-all text-accent underline underline-offset-4"
              >
                {rule.source_url}
              </a>
            </dd>
          </div>
        )}
      </dl>

      <label htmlFor={`why-${rule.rule_id}`} className="slate mt-4 block text-paper-400">
        Why (recorded on the passport)
      </label>
      <textarea
        id={`why-${rule.rule_id}`}
        rows={3}
        value={reason}
        onChange={(event) => setReason(event.target.value)}
        placeholder="The source states a minimum, not an exact value."
        className="mt-2 w-full rounded-[3px] border border-line bg-ink-100 px-3 py-2
                   text-sm text-paper-000 outline-none placeholder:text-paper-500
                   focus:border-line-strong"
      />

      {failure && (
        <p role="alert" className="mt-2 text-sm text-stop">
          {failure}
        </p>
      )}

      <div className="mt-3 flex flex-wrap gap-2">
        <button
          type="button"
          disabled={busy || reason.trim().length < 8}
          onClick={() => decide("set_aside")}
          className="rounded-[3px] border border-line-strong px-3.5 py-1.5 text-xs
                     text-paper-100 transition hover:bg-ink-200 disabled:opacity-40"
        >
          Set this requirement aside
        </button>
        {rule.disposition === "set_aside" && (
          <button
            type="button"
            disabled={busy || reason.trim().length < 8}
            onClick={() => decide("accept")}
            className="rounded-[3px] border border-line px-3.5 py-1.5 text-xs
                       text-paper-300 transition hover:text-paper-000 disabled:opacity-40"
          >
            Measure against it again
          </button>
        )}
        <button
          type="button"
          onClick={() => setOpen(false)}
          className="px-2 py-1.5 text-xs text-paper-400 hover:text-paper-100"
        >
          Cancel
        </button>
      </div>

      <p className="mt-3 text-xs text-paper-400">
        Setting a requirement aside does not delete it. It stays on record and
        appears in the release passport as a stated limitation.
      </p>
    </div>
  );
}
