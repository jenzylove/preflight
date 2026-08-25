"use client";

import Link from "next/link";
import { use, useCallback, useEffect, useState } from "react";

import { Shell } from "@/components/Shell";
import { api, type DeliveryRoom, type PackageSummary } from "@/lib/api";

/**
 * Packages, and the delivery rooms that share them.
 *
 * One package per destination. Where destinations conflict, the difference
 * between the packages is the product working — so they are listed separately
 * rather than merged into a single "output".
 *
 * A delivery room can only be created for a VERIFIED package. The button is
 * absent otherwise, and the API refuses regardless.
 */
export default function PackagesPage({
  params,
}: {
  params: Promise<{ projectId: string }>;
}) {
  const { projectId } = use(params);
  return (
    <Shell>
      <Packages projectId={projectId} />
    </Shell>
  );
}

function Packages({ projectId }: { projectId: string }) {
  const [packages, setPackages] = useState<PackageSummary[] | null>(null);
  const [rooms, setRooms] = useState<DeliveryRoom[]>([]);
  const [issued, setIssued] = useState<Record<string, string>>({});
  const [error, setError] = useState("");

  const load = useCallback(async () => {
    try {
      const [p, r] = await Promise.all([
        api.listPackages(projectId),
        api.listRooms(projectId).catch(() => []),
      ]);
      setPackages(p);
      setRooms(r);
    } catch (e) {
      setError(e instanceof Error ? e.message : "Could not load packages.");
    }
  }, [projectId]);

  useEffect(() => {
    load();
  }, [load]);

  async function createRoom(pkg: PackageSummary) {
    setError("");
    try {
      const room = await api.createRoom(projectId, pkg.id, {
        recipient_label: pkg.destination_name,
        expires_in_hours: 168,
      });
      if (room.url_token) {
        setIssued((s) => ({
          ...s,
          [pkg.id]: `${window.location.origin}/delivery/${room.url_token}`,
        }));
      }
      load();
    } catch (e) {
      setError(e instanceof Error ? e.message : "Could not create a delivery link.");
    }
  }

  async function download(pkg: PackageSummary) {
    try {
      const { url } = await api.packageDownload(projectId, pkg.id);
      window.open(url, "_blank", "noopener");
    } catch (e) {
      setError(e instanceof Error ? e.message : "Download is unavailable.");
    }
  }

  if (!packages) {
    return (
      <main className="mx-auto max-w-3xl px-6 py-12">
        <p className="text-neutral-500">Loading…</p>
      </main>
    );
  }

  return (
    <main className="mx-auto max-w-3xl px-6 py-10">
      <h1 className="text-2xl font-semibold text-neutral-100">Packages</h1>
      <p className="mt-2 text-sm text-neutral-400">
        One package per destination, each measured again after it was built.
      </p>

      {error && (
        <p role="alert" className="mt-4 text-sm text-rose-400">
          {error}
        </p>
      )}

      {packages.length === 0 && (
        <div className="mt-8 rounded-lg border border-dashed border-neutral-800 p-8 text-center">
          <p className="text-neutral-300">No packages have been built yet.</p>
          <Link
            href={`/projects/${projectId}/plan`}
            className="mt-2 inline-block text-sm text-sky-400 underline"
          >
            Review and approve the repair plan
          </Link>
        </div>
      )}

      <div className="mt-6 space-y-5">
        {packages.map((pkg) => (
          <section
            key={pkg.id}
            className="rounded-lg border border-neutral-800 bg-neutral-950 p-5"
          >
            <header className="flex flex-wrap items-baseline justify-between gap-2">
              <h2 className="text-lg font-medium text-neutral-100">
                {pkg.destination_name}
              </h2>
              <span
                className={`rounded px-2 py-0.5 text-xs font-medium ring-1 ring-inset ${
                  pkg.verified
                    ? "bg-emerald-950 text-emerald-300 ring-emerald-800"
                    : "bg-amber-950 text-amber-300 ring-amber-800"
                }`}
              >
                {pkg.verified ? "Meets published requirements" : pkg.state}
              </span>
            </header>

            <p className="mt-1 text-xs text-neutral-500">
              {pkg.requirements_satisfied} requirements satisfied
              {pkg.rule_pack_version
                ? ` · rule pack v${pkg.rule_pack_version} ${pkg.rule_pack_digest ?? ""}`
                : ""}
              {pkg.validator_version ? ` · validator ${pkg.validator_version}` : ""}
            </p>

            {pkg.package_sha256 && (
              <p className="mt-2 break-all font-mono text-xs text-neutral-500">
                package sha256 {pkg.package_sha256}
              </p>
            )}

            {pkg.transformations.length > 0 && (
              <details className="mt-3">
                <summary className="cursor-pointer text-sm text-neutral-400 hover:text-neutral-200">
                  What was changed ({pkg.transformations.length})
                </summary>
                <ul className="mt-2 space-y-2 border-l-2 border-neutral-800 pl-3">
                  {pkg.transformations.map((t, i) => (
                    <li key={i} className="text-xs">
                      <span className="font-mono text-neutral-200">{t.operation}</span>
                      {t.picture_preserved === true && (
                        <span className="ml-2 text-emerald-400">
                          picture unchanged
                        </span>
                      )}
                      <div className="mt-0.5 text-neutral-500">
                        {Object.entries(t.parameters)
                          .map(([k, v]) => `${k}=${String(v)}`)
                          .join(", ")}
                      </div>
                    </li>
                  ))}
                </ul>
              </details>
            )}

            {pkg.files.length > 0 && (
              <details className="mt-2">
                <summary className="cursor-pointer text-sm text-neutral-400 hover:text-neutral-200">
                  Contents ({pkg.files.length} files)
                </summary>
                <ul className="mt-2 space-y-1 border-l-2 border-neutral-800 pl-3">
                  {pkg.files.map((f) => (
                    <li key={f.path} className="text-xs">
                      <span className="text-neutral-300">{f.path}</span>
                      <div className="break-all font-mono text-neutral-600">
                        {f.sha256}
                      </div>
                    </li>
                  ))}
                </ul>
              </details>
            )}

            {pkg.limitations.length > 0 && (
              <div className="mt-3 rounded border border-amber-900/60 bg-amber-950/20 p-3">
                <p className="text-xs font-medium text-amber-200">Not resolved</p>
                <ul className="mt-1 space-y-0.5 text-xs text-neutral-300">
                  {pkg.limitations.map((l, i) => (
                    <li key={i}>{l}</li>
                  ))}
                </ul>
              </div>
            )}

            <div className="mt-4 flex flex-wrap gap-2">
              {pkg.package_sha256 && (
                <button
                  onClick={() => download(pkg)}
                  className="rounded border border-neutral-700 px-3 py-1.5 text-sm
                             text-neutral-200 hover:border-neutral-500"
                >
                  Download
                </button>
              )}
              {pkg.verified && (
                <button
                  onClick={() => createRoom(pkg)}
                  className="rounded bg-neutral-100 px-3 py-1.5 text-sm font-medium
                             text-neutral-950 hover:bg-white"
                >
                  Create delivery link
                </button>
              )}
            </div>

            {issued[pkg.id] && (
              <div className="mt-3 rounded border border-sky-900 bg-sky-950/30 p-3">
                <p className="text-xs text-sky-200">
                  Copy this now — it is shown once and cannot be recovered.
                </p>
                <code className="mt-1 block break-all text-xs text-neutral-100">
                  {issued[pkg.id]}
                </code>
              </div>
            )}
          </section>
        ))}
      </div>

      {rooms.length > 0 && (
        <section className="mt-10 border-t border-neutral-900 pt-6">
          <h2 className="text-sm font-medium uppercase tracking-wide text-neutral-500">
            Delivery links
          </h2>
          <ul className="mt-3 space-y-2">
            {rooms.map((room) => (
              <li
                key={room.room_id}
                className="flex flex-wrap items-baseline justify-between gap-2
                           rounded border border-neutral-800 p-3 text-sm"
              >
                <span className="text-neutral-300">
                  {room.recipient_label ?? "Unlabelled"}
                  <span className="ml-2 text-xs text-neutral-500">{room.state}</span>
                </span>
                {room.state === "active" && (
                  <button
                    onClick={async () => {
                      await api.revokeRoom(projectId, room.room_id);
                      load();
                    }}
                    className="text-xs text-rose-400 underline"
                  >
                    Revoke
                  </button>
                )}
              </li>
            ))}
          </ul>
        </section>
      )}

      {packages.length > 0 && (
        <Link
          href={`/projects/${projectId}/passport`}
          className="mt-8 inline-block text-sky-400 underline underline-offset-2"
        >
          Open the release passport
        </Link>
      )}
    </main>
  );
}
