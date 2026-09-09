"use client";

import Link from "next/link";
import { use, useCallback, useEffect, useState } from "react";

import { StatusChip } from "@/components/Status";
import { ProjectRail } from "@/components/workspace/Rail";
import { Workspace } from "@/components/workspace/Workspace";
import { api } from "@/lib/api";
import {
  fieldLabel,
  formatValue,
  operationDone,
} from "@/lib/language";
import type {
  DeliveryRoom,
  OutstandingCheck,
  PackageSummary,
  Project,
} from "@/lib/types";

/**
 * What was produced, and whether it survived being checked again.
 *
 * One package per destination. Where two destinations want incompatible
 * things, two packages exist, and the reason is on the screen rather than left
 * for the user to infer from a duplicate row.
 *
 * A package that did not verify is not a failure state to be softened. It is
 * the product working: something remains unresolved, it is named, and nothing
 * claims to be ready.
 */
export default function PackagesPage({
  params,
}: {
  params: Promise<{ projectId: string }>;
}) {
  const { projectId } = use(params);
  return (
    <Workspace wide>
      <Packages projectId={projectId} />
    </Workspace>
  );
}

function Packages({ projectId }: { projectId: string }) {
  const [project, setProject] = useState<Project | null>(null);
  const [packages, setPackages] = useState<PackageSummary[]>([]);
  const [rooms, setRooms] = useState<DeliveryRoom[]>([]);
  const [error, setError] = useState<string | null>(null);

  const load = useCallback(async () => {
    const [p, pkgs, existing] = await Promise.all([
      api.getProject(projectId),
      api.listPackages(projectId).catch(() => [] as PackageSummary[]),
      api.listRooms(projectId).catch(() => [] as DeliveryRoom[]),
    ]);
    setProject(p);
    setPackages(pkgs);
    setRooms(existing);
  }, [projectId]);

  useEffect(() => {
    load().catch((caught) =>
      setError(caught instanceof Error ? caught.message : "Could not load packages."),
    );
  }, [load]);

  if (!project) {
    return <p className="slate text-paper-400" role="status">Loading</p>;
  }

  return (
    <>
      <ProjectRail project={project} />

      <div className="mb-8">
        <h2 className="font-display text-2xl text-paper-000">
          {packages.length === 0
            ? "Nothing has been built yet"
            : "Rechecked, from the files themselves"}
        </h2>
        <p className="mt-3 max-w-measure text-[15px] leading-relaxed text-paper-300">
          Preflight does not take the worker&rsquo;s word for it. Every package
          below was re-opened after it was built and measured again from
          scratch, against the same published requirements.
        </p>
      </div>

      {error && (
        <p role="alert" className="border-l-2 border-stop bg-stop-bg/40 py-3 pl-4 text-paper-100">
          {error}
        </p>
      )}

      {packages.length === 0 && !error && (
        <p className="text-paper-300">
          Approve a repair plan and run it to produce packages.
        </p>
      )}

      {packages.length > 1 && (
        <p className="mb-6 rounded-[3px] border border-line bg-ink-100 px-4 py-3 text-sm text-paper-300">
          These destinations require different deliverables, so each gets its
          own package built from your master.
        </p>
      )}

      <div className="space-y-6">
        {packages.map((pkg) => (
          <PackageCard
            key={pkg.id}
            pkg={pkg}
            projectId={projectId}
            rooms={rooms}
            onChanged={load}
          />
        ))}
      </div>

      {packages.length > 0 && (
        <div className="mt-10 flex justify-end">
          <Link
            href={`/projects/${projectId}/passport`}
            className="rounded-[3px] bg-paper-000 px-5 py-2.5 text-sm font-medium
                       text-ink-000 transition hover:bg-white"
          >
            View package proof
          </Link>
        </div>
      )}
    </>
  );
}

type PackageTask = {
  key: string;
  label: string;
  summary: string;
  buttonLabel: string;
  href: string;
  checks: OutstandingCheck[];
};

function buildPackageTasks(
  checks: OutstandingCheck[],
  destination: string,
  projectId: string,
): PackageTask[] {
  const grouped = new Map<string, OutstandingCheck[]>();
  for (const check of checks) {
    const key = packageTaskKey(check);
    grouped.set(key, [...(grouped.get(key) ?? []), check]);
  }

  return [...grouped.entries()].map(([key, groupedChecks]) => ({
    key,
    label: packageTaskLabel(key, groupedChecks),
    summary: packageTaskSummary(key, destination),
    buttonLabel: key === "delivery-review" || key === "audio-dynamics" ? "Review" : "Resolve",
    href: packageTaskHref(key, projectId),
    checks: groupedChecks,
  }));
}

function packageTaskKey(check: OutstandingCheck): string {
  if (check.asset_type === "audio" && check.field === "channels") return "audio-mix";
  if (
    check.asset_type === "audio"
    && ["codec", "sampleRateHz", "bitrateBps"].includes(check.field)
  ) return "audio-format";
  if (
    check.asset_type === "audio"
    && ["integratedLoudnessLufs", "truePeakDbtp", "loudnessRangeLu"].includes(check.field)
  ) return "audio-dynamics";
  if (check.asset_type === "video") return "video-requirements";
  if (check.asset_type === "subtitle") return "subtitles";
  if (check.asset_type === "package" && check.result === "AMBIGUOUS") return "delivery-review";
  if (check.asset_type === "package" || check.asset_type === "metadata") return "delivery-details";
  return `${check.asset_type}-${check.field}`;
}

function packageTaskLabel(key: string, checks: OutstandingCheck[]): string {
  if (key === "audio-mix") return "Audio mix";
  if (key === "audio-format") return "Audio format";
  if (key === "audio-dynamics") return "Audio dynamic range";
  if (key === "video-requirements") return "Video requirements";
  if (key === "subtitles") return "Subtitles";
  if (key === "delivery-review") return "Review delivery requirement";
  if (key === "delivery-details") return "Delivery details";
  return fieldLabel(checks[0]?.asset_type ?? "file", checks[0]?.field ?? "requirement");
}

function packageTaskSummary(key: string, destination: string): string {
  if (key === "audio-mix") return `The prepared file does not yet contain ${destination}’s required channel mix.`;
  if (key === "audio-format") return `The prepared file does not yet match ${destination}’s accepted audio format.`;
  if (key === "audio-dynamics") return "This audio requirement needs review before delivery.";
  if (key === "video-requirements") return "Some video delivery requirements are still unmet.";
  if (key === "subtitles") return `${destination}’s subtitle requirements are still unmet.`;
  if (key === "delivery-review") return "A published delivery requirement needs review before this package can be verified.";
  if (key === "delivery-details") return "Some delivery details still need attention.";
  return "This requirement still needs attention before delivery.";
}

function packageTaskHref(key: string, projectId: string): string {
  if (key === "delivery-details") return `/projects/${projectId}/destinations`;
  if (key === "delivery-review") return `/projects/${projectId}/preflight`;
  return `/projects/${projectId}/master#master-upload`;
}

function PackageTaskCard({ task }: { task: PackageTask }) {
  return (
    <li className="rounded-[3px] bg-ink-000/45 px-4 py-4">
      <div className="flex flex-wrap items-baseline justify-between gap-3">
        <h5 className="text-sm font-medium text-paper-000">{task.label}</h5>
        <Link
          href={task.href}
          className="rounded-[3px] border border-line-strong px-3.5 py-2 text-sm
                     text-paper-100 transition hover:bg-ink-200"
        >
          {task.buttonLabel}
        </Link>
      </div>
      <p className="mt-2 max-w-measure text-sm leading-relaxed text-paper-200">
        {task.summary}
      </p>
    </li>
  );
}

function RemainingChecks({ tasks }: { tasks: PackageTask[] }) {
  const count = tasks.reduce((total, task) => total + task.checks.length, 0);
  if (count === 0) return null;

  return (
    <details className="mb-5">
      <summary className="cursor-pointer text-sm text-paper-200 hover:text-paper-000">
        Remaining checks ({count})
      </summary>
      <div className="mt-4 space-y-5">
        {tasks.map((task) => (
          <section key={task.key}>
            <h5 className="text-sm font-medium text-paper-200">
              {task.label} <span className="font-normal text-paper-400">({task.checks.length})</span>
            </h5>
            <ul className="mt-2 space-y-2 border-l border-line pl-4">
              {task.checks.map((check, index) => (
                <li key={`${check.asset_type}.${check.field}-${index}`} className="text-xs leading-relaxed">
                  <p className="font-medium text-paper-200">
                    {check.asset_type}.{check.field}
                  </p>
                  <p className="text-paper-400">
                    Published: <span className="font-mono text-paper-300">{check.published}</span>
                    {" · "}
                    Measured: <span className="font-mono text-paper-300">
                      {check.measured == null ? "not measured" : formatValue(check.measured, check.field)}
                    </span>
                    {" · "}
                    Result: <span className="font-mono text-paper-300">{check.result}</span>
                  </p>
                </li>
              ))}
            </ul>
          </section>
        ))}
      </div>
    </details>
  );
}

function PackageContents({ pkg }: { pkg: PackageSummary }) {
  if (pkg.files.length === 0) return null;

  return (
    <details className="mb-5">
      <summary className="cursor-pointer text-sm text-paper-200 hover:text-paper-000">
        Package contents · {pkg.files.length} file{pkg.files.length === 1 ? "" : "s"}
      </summary>
      <ul className="mt-4 space-y-3">
        {pkg.files.map((file) => (
          <li key={file.path} className="border-b border-line/60 pb-3 text-sm text-paper-200">
            <span>{packageFileLabel(file.path)}</span>
            <details className="mt-2">
              <summary className="cursor-pointer text-xs text-paper-400 hover:text-paper-200">
                Technical details
              </summary>
              <dl className="mt-2 space-y-1 border-l border-line pl-3 text-xs">
                <Row label="Path" value={file.path} mono />
                <Row label="sha256" value={file.sha256} mono />
              </dl>
            </details>
          </li>
        ))}
      </ul>
    </details>
  );
}

function packageFileLabel(path: string): string {
  const lower = path.toLowerCase();
  if (lower.endsWith("manifest.json")) return "Manifest";
  if (lower.endsWith(".mov") || lower.endsWith(".mp4")) return "Prepared film";
  if (lower.endsWith(".srt") || lower.endsWith(".vtt")) return "Subtitle file";
  if (/\.(jpg|jpeg|png)$/.test(lower)) return "Poster";
  return "Package file";
}

function PackageCard({
  pkg,
  projectId,
  rooms,
  onChanged,
}: {
  pkg: PackageSummary;
  projectId: string;
  rooms: DeliveryRoom[];
  onChanged: () => Promise<void>;
}) {
  const destinationName = pkg.destination_name || pkg.destination_id;

  const fixed = pkg.transformations;
  const tasks = buildPackageTasks(pkg.outstanding, destinationName, projectId);
  const checksSummary = pkg.checks_total > 0
    ? `${pkg.checks_passed} of ${pkg.checks_total} required checks pass`
    : pkg.requirements_satisfied;

  return (
    <section className="rounded-[3px] border border-line bg-ink-100">
      {/* The verdict first, in a sentence about the film. This screen used to
          open with a destination slug and a fraction, then list
          "subtitle.cueCount (NOT_MEASURED)" as the outcome of somebody's
          delivery. */}
      <header className="border-b border-line px-6 py-5">
        <p className="slate text-paper-400">{destinationName} package</p>
        <h3 className="font-display text-xl leading-snug text-paper-000">
          {pkg.verified ? `Verified for ${destinationName}` : "Prepared — not ready for delivery"}
        </h3>
        <p className="mt-2 text-sm text-paper-300">
          {checksSummary}
        </p>
        {!pkg.verified && (
          <p className="mt-1 text-sm text-paper-300">
            {pkg.outstanding.length} blocker{pkg.outstanding.length === 1 ? "" : "s"} remain
          </p>
        )}

        <div className="mt-5 flex flex-wrap items-center gap-3">
          <DownloadPackage pkg={pkg} projectId={projectId} />
          <Link
            href={`/projects/${projectId}/passport`}
            className="rounded-[3px] border border-line-strong px-4 py-2 text-sm
                       text-paper-100 transition hover:bg-ink-200"
          >
            View package proof
          </Link>
          {!pkg.verified && pkg.outstanding.length > 0 && (
            <Link
              href={`/projects/${projectId}/preflight`}
              className="text-sm text-paper-300 underline underline-offset-4
                         transition hover:text-paper-100"
            >
              Resolve remaining issues
            </Link>
          )}
        </div>
      </header>

      <div className="px-5 py-5">
        {fixed.length > 0 && (
          <section className="mb-8 rounded-[3px] border border-line bg-ink-000/35 px-4 py-4">
            <div className="flex flex-wrap items-baseline justify-between gap-3">
              <h4 className="text-sm font-medium text-paper-000">What Preflight changed</h4>
              <span className="text-sm text-paper-400">
                {fixed.length} change{fixed.length === 1 ? "" : "s"} made
              </span>
            </div>
            <ul className="mt-3 space-y-1.5 text-sm text-paper-200">
              {fixed.map((transformation, index) => (
                <li key={index}>• {operationDone(transformation.operation)}</li>
              ))}
            </ul>
          </section>
        )}

        {tasks.length > 0 && (
          <section className="mb-8">
            <div className="flex flex-wrap items-baseline justify-between gap-3">
              <h4 className="text-sm font-medium text-paper-000">What still blocks delivery</h4>
              <span className="text-sm text-paper-400">
                {tasks.length} thing{tasks.length === 1 ? "" : "s"} still need attention
              </span>
            </div>
            <ul className="mt-3 space-y-3">
              {tasks.map((task) => <PackageTaskCard key={task.key} task={task} />)}
            </ul>
          </section>
        )}

        <RemainingChecks tasks={tasks} />
        <PackageContents pkg={pkg} />

        {pkg.limitations.length > 0 && (
          <details className="mb-5">
            <summary className="cursor-pointer text-xs text-paper-400 hover:text-paper-200">
              Stated limitations ({pkg.limitations.length})
            </summary>
            <ul className="mt-3 space-y-2 border-l border-line pl-4">
              {pkg.limitations.map((limitation, index) => (
                <li key={index} className="text-sm leading-relaxed text-paper-300">
                  {limitation}
                </li>
              ))}
            </ul>
          </details>
        )}

        <details className="mb-5">
          <summary className="cursor-pointer text-sm text-paper-200 hover:text-paper-000">
            Technical details
          </summary>
          <div className="mt-4 space-y-4 border-l border-line pl-4 text-xs">
            <h5 className="text-sm font-medium text-paper-200">Transformations</h5>
            {fixed.length === 0 && <p className="text-paper-400">No transformations recorded.</p>}
            {fixed.map((transformation, index) => (
              <div key={index}>
                <p className="font-mono text-paper-200">{transformation.operation}</p>
                <dl className="mt-2 space-y-1">
                  <Row label="Input sha256" value={transformation.input_sha256} mono />
                  <Row label="Output sha256" value={transformation.output_sha256} mono />
                  <Row label="Picture preserved" value={transformation.picture_preserved == null ? null : String(transformation.picture_preserved)} />
                </dl>
                <pre className="mt-2 overflow-x-auto whitespace-pre-wrap font-mono text-[11px] leading-relaxed text-paper-400">
                  {JSON.stringify(transformation.parameters, null, 2)}
                </pre>
              </div>
            ))}
          </div>
        </details>

        <details className="mb-5">
          <summary className="cursor-pointer text-xs text-paper-400 hover:text-paper-200">
            Provenance
          </summary>
          <dl className="mt-3 space-y-1.5 border-l border-line pl-4 text-xs">
            <Row label="Package hash" value={pkg.package_sha256} mono />
            <Row label="Rule pack" value={pkg.rule_pack_digest} mono />
            <Row label="Rule pack version" value={pkg.rule_pack_version} />
            <Row label="Checked by" value={pkg.validator_version} mono />
            <Row label="State" value={pkg.state} />
          </dl>
        </details>

        {pkg.verified && (
          <Delivery
            pkg={pkg}
            projectId={projectId}
            rooms={rooms}
            onChanged={onChanged}
          />
        )}
      </div>
    </section>
  );
}

function DownloadPackage({
  pkg,
  projectId,
}: {
  pkg: PackageSummary;
  projectId: string;
}) {
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState<string | null>(null);

  async function download() {
    setBusy(true);
    setError(null);
    try {
      const intent = await api.packageDownload(projectId, pkg.id);
      window.location.assign(intent.url);
    } catch (caught) {
      setError(
        caught instanceof Error ? caught.message : "Could not prepare the package download.",
      );
      setBusy(false);
    }
  }

  return (
    <div>
      <button
        type="button"
        onClick={() => void download()}
        disabled={busy}
        className="rounded-[3px] bg-paper-000 px-4 py-2 text-sm font-medium
                   text-ink-000 transition hover:bg-white disabled:opacity-50"
      >
        {busy
          ? "Preparing…"
          : pkg.verified
            ? "Download verified package"
            : "Download prepared package"}
      </button>
      {error && (
        <p role="alert" className="mt-2 text-xs text-stop">
          {error}
        </p>
      )}
    </div>
  );
}

/**
 * Creating and managing a delivery room.
 *
 * The link is shown once. It is not recoverable afterwards because only its
 * hash is stored, which is the property that makes a leaked database useless.
 * Saying so at the moment of creation is more useful than explaining it later
 * when someone asks where their link went.
 */
function Delivery({
  pkg,
  projectId,
  rooms,
  onChanged,
}: {
  pkg: PackageSummary;
  projectId: string;
  rooms: DeliveryRoom[];
  onChanged: () => Promise<void>;
}) {
  const [label, setLabel] = useState("");
  const [busy, setBusy] = useState(false);
  const [created, setCreated] = useState<DeliveryRoom | null>(null);
  const [copied, setCopied] = useState(false);
  const [error, setError] = useState<string | null>(null);

  const live = rooms.filter((room) => room.state === "active");

  async function create() {
    setBusy(true);
    setError(null);
    try {
      const room = await api.createRoom(projectId, pkg.id, {
        recipient_label: label || undefined,
      });
      setCreated(room);
      await onChanged();
    } catch (caught) {
      setError(
        caught instanceof Error ? caught.message : "That link was not created.",
      );
    } finally {
      setBusy(false);
    }
  }

  async function revoke(roomId: string) {
    try {
      await api.revokeRoom(projectId, roomId);
      await onChanged();
    } catch (caught) {
      setError(caught instanceof Error ? caught.message : "Could not revoke that link.");
    }
  }

  const url =
    created?.url_token != null
      ? `${typeof window === "undefined" ? "" : window.location.origin}/delivery/${created.url_token}`
      : null;

  return (
    <div className="border-t border-line pt-5">
      <h4 className="slate mb-3 text-paper-400">Send it</h4>

      {url ? (
        <div className="rounded-[3px] border border-line-strong bg-ink-000 p-4">
          <p className="text-sm text-paper-100">
            Copy this link now. It is shown once and cannot be shown again.
          </p>
          <div className="mt-3 flex flex-wrap gap-2">
            <code className="flex-1 overflow-x-auto whitespace-nowrap rounded-[3px]
                             border border-line bg-ink-100 px-3 py-2 font-mono text-xs text-paper-100">
              {url}
            </code>
            <button
              type="button"
              onClick={() => {
                void navigator.clipboard.writeText(url);
                setCopied(true);
              }}
              className="rounded-[3px] border border-line-strong px-3.5 py-2 text-xs
                         text-paper-100 transition hover:bg-ink-200"
            >
              {copied ? "Copied" : "Copy"}
            </button>
          </div>
          <p className="mt-3 text-xs text-paper-400">{created?.note}</p>
        </div>
      ) : (
        <div className="flex flex-wrap items-end gap-3">
          <div className="min-w-[14rem] flex-1">
            <label htmlFor={`who-${pkg.id}`} className="slate block text-paper-400">
              Who is this for (optional)
            </label>
            <input
              id={`who-${pkg.id}`}
              value={label}
              onChange={(event) => setLabel(event.target.value)}
              placeholder="Artdocfest programming"
              className="mt-2 w-full rounded-[3px] border border-line bg-ink-000 px-3 py-2
                         text-sm text-paper-000 outline-none placeholder:text-paper-500
                         focus:border-line-strong"
            />
          </div>
          <button
            type="button"
            onClick={create}
            disabled={busy}
            className="rounded-[3px] border border-line-strong px-4 py-2 text-sm
                       text-paper-100 transition hover:bg-ink-200 disabled:opacity-50"
          >
            {busy ? "Creating…" : "Create a delivery link"}
          </button>
        </div>
      )}

      {error && (
        <p role="alert" className="mt-3 text-sm text-stop">
          {error}
        </p>
      )}

      {live.length > 0 && (
        <ul className="mt-4 space-y-2">
          {live.map((room) => (
            <li
              key={room.room_id}
              className="flex flex-wrap items-center justify-between gap-3 border-b
                         border-line/60 pb-2 text-sm"
            >
              <span className="text-paper-200">
                {room.recipient_label || "Unlabelled link"}
                <span className="ml-3 text-xs text-paper-400">
                  expires {new Date(room.expires_at).toLocaleDateString()}
                </span>
              </span>
              <button
                type="button"
                onClick={() => revoke(room.room_id)}
                className="text-xs text-paper-400 transition hover:text-stop"
              >
                Revoke
              </button>
            </li>
          ))}
        </ul>
      )}
    </div>
  );
}

function Row({
  label,
  value,
  mono,
}: {
  label: string;
  value: string | number | null;
  mono?: boolean;
}) {
  if (value === null || value === undefined || value === "") return null;
  return (
    <div className="flex items-baseline justify-between gap-4">
      <dt className="text-paper-400">{label}</dt>
      <dd className={`break-all text-right text-paper-100 ${mono ? "font-mono" : ""}`}>
        {String(value)}
      </dd>
    </div>
  );
}
