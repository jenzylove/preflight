"use client";

import Link from "next/link";
import { use, useCallback, useEffect, useState } from "react";

import { StatusChip } from "@/components/Status";
import { ProjectRail } from "@/components/workspace/Rail";
import { Workspace } from "@/components/workspace/Workspace";
import { api } from "@/lib/api";
import type { DeliveryRoom, PackageSummary, Project } from "@/lib/types";

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
  return (
    <section className="rounded-[3px] border border-line bg-ink-100">
      <header className="flex flex-wrap items-start justify-between gap-4 border-b border-line px-5 py-4">
        <div>
          <h3 className="font-display text-lg text-paper-000">
            {pkg.destination_name || pkg.destination_id}
          </h3>
          <p className="mt-1 text-sm text-paper-300">
            {pkg.requirements_satisfied} requirements satisfied
          </p>
        </div>
        {pkg.verified ? (
          <StatusChip tone="ok">Ready against current published requirements</StatusChip>
        ) : (
          <StatusChip tone="act">Not ready</StatusChip>
        )}
      </header>

      <div className="px-5 py-5">
        {!pkg.verified && pkg.limitations.length > 0 && (
          <div className="mb-5 rounded-[3px] border-l-2 border-review bg-review-bg/20 py-3 pl-4 pr-4">
            <p className="text-sm text-paper-100">What is still outstanding</p>
            <ul className="mt-2 space-y-1.5">
              {pkg.limitations.map((limitation, index) => (
                <li key={index} className="text-sm leading-relaxed text-paper-300">
                  {limitation}
                </li>
              ))}
            </ul>
          </div>
        )}

        {pkg.transformations.length > 0 && (
          <div className="mb-5">
            <h4 className="slate mb-2 text-paper-400">What changed</h4>
            <ul className="space-y-2">
              {pkg.transformations.map((t, index) => (
                <li key={index} className="text-sm">
                  <span className="font-mono text-paper-100">{t.operation}</span>
                  {t.picture_preserved === true && (
                    <span className="ml-3 text-paper-300">
                      picture bit-identical to your original
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
