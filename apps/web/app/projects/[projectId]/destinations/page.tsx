"use client";

import Link from "next/link";
import { use, useState } from "react";

import { Shell } from "@/components/Shell";
import { API_BASE } from "@/lib/api";

/**
 * Destination selection.
 *
 * The two destinations below are the ones Preflight has verified it can
 * actually read. That distinction is the product: a destination whose
 * requirements are published behind a login or rendered by script cannot be
 * retrieved, and saying so is more useful than offering it and failing later.
 */

const AVAILABLE = [
  {
    id: "berlinale",
    name: "Berlinale",
    kind: "Festival · Berlin",
    source:
      "https://www.berlinale.de/en/film-entry/technical-specifications/festival-media.html",
    note: "DCP or QuickTime ProRes. Subtitles must be burned into the picture — sidecar files are not accepted.",
  },
  {
    id: "artdocfest",
    name: "Artdocfest",
    kind: "Festival · Documentary",
    source: "https://artdocfest.com/en/content/technical-requirements/",
    note: "H.264 in MP4 or MOV, 20–30 Mbps, integrated loudness −18 to −21 LUFS. SubRip sidecar; burned-in subtitles are not allowed.",
  },
] as const;

const UNREADABLE = [
  {
    name: "Netflix",
    reason: "Delivery specifications require partner login.",
  },
  {
    name: "YouTube",
    reason:
      "The encoding specification is rendered by script. Retrieval returns prose with no bitrate, frame rate or aspect ratio in it.",
  },
] as const;

export default function DestinationsPage({
  params,
}: {
  params: Promise<{ projectId: string }>;
}) {
  const { projectId } = use(params);
  return (
    <Shell>
      <Destinations projectId={projectId} />
    </Shell>
  );
}

function Destinations({ projectId }: { projectId: string }) {
  const [chosen, setChosen] = useState<string[]>(["berlinale", "artdocfest"]);

  const toggle = (id: string) =>
    setChosen((c) => (c.includes(id) ? c.filter((x) => x !== id) : [...c, id]));

  return (
    <main className="mx-auto max-w-3xl px-6 py-10">
      <h1 className="text-2xl font-semibold text-neutral-100">
        Where is this going?
      </h1>
      <p className="mt-2 text-sm text-neutral-400">
        Preflight retrieves each destination&apos;s current published requirements
        through Parallel, extracts them into a strict schema with Gemini, and
        records the source and retrieval date for every rule.
      </p>

      <ul className="mt-8 space-y-3">
        {AVAILABLE.map((d) => {
          const on = chosen.includes(d.id);
          return (
            <li key={d.id}>
              <button
                onClick={() => toggle(d.id)}
                aria-pressed={on}
                className={`w-full rounded-lg border p-4 text-left transition ${
                  on
                    ? "border-neutral-500 bg-neutral-900"
                    : "border-neutral-800 hover:border-neutral-700"
                }`}
              >
                <div className="flex items-baseline justify-between gap-3">
                  <span className="font-medium text-neutral-100">{d.name}</span>
                  <span className="text-xs text-neutral-500">{d.kind}</span>
                </div>
                <p className="mt-1.5 text-sm text-neutral-400">{d.note}</p>
                <p className="mt-2 break-all text-xs text-sky-400">{d.source}</p>
              </button>
            </li>
          );
        })}
      </ul>

      {chosen.length === 2 && (
        <div className="mt-6 rounded-lg border border-rose-900 bg-rose-950/30 p-4">
          <p className="text-sm font-medium text-neutral-100">
            These two cannot both be satisfied by one set of files
          </p>
          <p className="mt-1.5 text-sm text-neutral-400">
            The Berlinale requires subtitles burned into the picture. Artdocfest
            forbids exactly that and requires a SubRip sidecar. Preflight will build
            a separate version for each and cite the sentence behind both.
          </p>
        </div>
      )}

      <div className="mt-8 flex flex-wrap gap-3">
        <Link
          href={`/projects/${projectId}/preflight`}
          className="rounded bg-neutral-100 px-5 py-2 font-medium text-neutral-950
                     transition hover:bg-white"
        >
          Run preflight
        </Link>
        <Link
          href={`/projects/${projectId}/master`}
          className="rounded border border-neutral-700 px-5 py-2 text-neutral-300
                     transition hover:border-neutral-500"
        >
          Back to files
        </Link>
      </div>

      <section className="mt-12 border-t border-neutral-900 pt-6">
        <h2 className="text-sm font-medium uppercase tracking-wide text-neutral-500">
          Destinations Preflight cannot read
        </h2>
        <p className="mt-2 text-sm text-neutral-400">
          These publish authoritatively but not in a form any retrieval tool can
          parse. For these, upload the specification you already hold — it is marked
          private and never sent to a retrieval provider.
        </p>
        <ul className="mt-3 space-y-2">
          {UNREADABLE.map((d) => (
            <li key={d.name} className="text-sm">
              <span className="text-neutral-300">{d.name}</span>
              <span className="text-neutral-500"> — {d.reason}</span>
            </li>
          ))}
        </ul>
      </section>

      <p className="mt-10 text-xs text-neutral-600">
        Rules and evidence are served by {API_BASE}
      </p>
    </main>
  );
}
