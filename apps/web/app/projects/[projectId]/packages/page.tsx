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
  requirementSentence,
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

  const verified = packages.filter((p) => p.verified);

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

      {verified.length > 0 && (
        <div className="mt-10 flex justify-end">
          <Link
            href={`/projects/${projectId}/passport`}
            className="rounded-[3px] bg-paper-000 px-5 py-2.5 text-sm font-medium
                       text-ink-000 transition hover:bg-white"
          >
            Open the release passport
          </Link>
        </div>
      )}
    </>
  );
}

/**
 * One class of unfinished business, in sentences.
 *
 * Each entry says what the destination asks for and what the film currently
 * is. The field path, the comparison result and the exact published value are
 * still available, one disclosure deeper, because they are the evidence.
 */
function OutstandingGroup({
  title,
  blurb,
  checks,
  destination,
}: {
  title: string;
  blurb: string;
  checks: OutstandingCheck[];
  destination: string;
}) {
  if (checks.length === 0) return null;

  return (
    <div className="mb-6">
      <h4 className="text-sm font-medium text-paper-100">
        {title}
        <span className="ml-2 font-normal text-paper-400">{checks.length}</span>
      </h4>
      <p className="mt-1 max-w-measure text-sm leading-relaxed text-paper-400">
        {blurb}
      </p>
      <ul className="mt-3 space-y-2.5">
        {checks.map((check, index) => (
          <li key={`${check.asset_type}.${check.field}-${index}`}
              className="rounded-[3px] bg-ink-000/40 px-4 py-3">
            <p className="text-sm font-medium text-paper-000">
              {fieldLabel(check.asset_type, check.field)}
            </p>
            <p className="mt-1 max-w-measure text-sm leading-relaxed text-paper-200">
              {requirementSentence(
                destination,
                check.asset_type,
                check.field,
                "eq",
                check.published,
              )}{" "}
              {check.measured ? (
                <span className="text-paper-300">
                  Your film is {formatValue(check.measured, check.field)}.
                </span>
              ) : (
                <span className="text-paper-400">
                  Preflight has not measured this on your files.
                </span>
              )}
            </p>
            <details className="mt-2">
              <summary className="cursor-pointer text-xs text-paper-400 transition hover:text-paper-200">
                Technical details
              </summary>
              <dl className="mt-2 grid gap-x-8 gap-y-1 border-l border-line pl-3 text-xs sm:grid-cols-2">
                <div>
                  <dt className="inline text-paper-400">Field: </dt>
                  <dd className="inline font-mono text-paper-200">
                    {check.asset_type}.{check.field}
                  </dd>
                </div>
                <div>
                  <dt className="inline text-paper-400">Result: </dt>
                  <dd className="inline font-mono text-paper-200">{check.result}</dd>
                </div>
                <div>
                  <dt className="inline text-paper-400">Published: </dt>
                  <dd className="inline font-mono text-paper-200">{check.published}</dd>
                </div>
                <div>
                  <dt className="inline text-paper-400">Measured: </dt>
                  <dd className="inline font-mono text-paper-200">
                    {check.measured ?? "not measured"}
                  </dd>
                </div>
              </dl>
            </details>
          </li>
        ))}
      </ul>
    </div>
  );
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

  // Grouped by what the person has to do, which is the only ordering that
  // helps. The raw result enums stay under technical details.
  const decisions = pkg.outstanding.filter((c) => c.result === "REVIEW_REQUIRED");
  const missing = pkg.outstanding.filter(
    (c) => c.result === "NOT_MEASURED" || c.result === "AMBIGUOUS",
  );
  const external = pkg.outstanding.filter((c) => c.result === "UNSUPPORTED");
  const fixed = pkg.transformations;

  return (
    <section className="rounded-[3px] border border-line bg-ink-100">
      {/* The verdict first, in a sentence about the film. This screen used to
          open with a destination slug and a fraction, then list
          "subtitle.cueCount (NOT_MEASURED)" as the outcome of somebody's
          delivery. */}
      <header className="border-b border-line px-6 py-5">
        <h3 className="font-display text-xl leading-snug text-paper-000">
          {pkg.verified
            ? `Your ${destinationName} package is ready`
            : `Your ${destinationName} package is not ready yet`}
        </h3>
        <p className="mt-2 text-sm text-paper-300">
          {pkg.checks_total > 0
            ? `${pkg.checks_passed} of ${pkg.checks_total} required checks pass`
            : pkg.requirements_satisfied}
          {fixed.length > 0 && (
            <>
              {" · "}
              Preflight safely fixed {fixed.length}{" "}
              {fixed.length === 1 ? "issue" : "issues"}
            </>
          )}
        </p>

        {!pkg.verified && decisions.length > 0 && (
          <Link
            href={`/projects/${projectId}/preflight`}
            className="mt-4 inline-block rounded-[3px] bg-paper-000 px-4 py-2 text-sm
                       font-medium text-ink-000 transition hover:bg-white"
          >
            Resolve remaining issues
          </Link>
        )}
      </header>

      <div className="px-5 py-5">
        <OutstandingGroup
          title="Needs your decision"
          blurb="Changes to the film itself. Preflight will not make these for you."
          checks={decisions}
          destination={destinationName}
        />
        <OutstandingGroup
          title="Needs information or files from you"
          blurb="Preflight could not check these because it was not given what it needs."
          checks={missing}
          destination={destinationName}
        />
        <OutstandingGroup
          title="Must be handled outside Preflight"
          blurb="No safe operation exists for these, so they need work elsewhere."
          checks={external}
          destination={destinationName}
        />

        {fixed.length > 0 && (
          <div className="mb-5">
            <h4 className="text-sm font-medium text-paper-100">Already fixed</h4>
            <ul className="mt-2 space-y-1.5">
              {fixed.map((t, index) => (
                <li key={index} className="text-sm text-paper-300">
                  {operationDone(t.operation)}
                  {t.picture_preserved === true && (
                    <span className="text-paper-400">
                      {" "}
                      — your picture is bit-identical to the original
                    </span>
                  )}
                </li>
              ))}
            </ul>
          </div>
        )}

        {pkg.files.length > 0 && (
          <div className="mb-5">
            <h4 className="slate mb-2 text-paper-400">
              {pkg.files.length} file{pkg.files.length === 1 ? "" : "s"}
            </h4>
            <ul className="space-y-1">
              {pkg.files.map((file) => (
                <li
                  key={file.path}
                  className="flex flex-wrap items-baseline justify-between gap-x-4 gap-y-0.5
                             border-b border-line/60 pb-1"
                >
                  <span className="font-mono text-[13px] text-paper-100">
                    {file.path}
                  </span>
                  <span className="font-mono text-[11px] text-paper-500">
                    {file.sha256.slice(0, 16)}…
                  </span>
                </li>
              ))}
            </ul>
          </div>
        )}

        {pkg.verified && pkg.limitations.length > 0 && (
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
