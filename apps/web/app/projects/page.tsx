"use client";

import Link from "next/link";
import { useEffect, useState } from "react";

import { Shell } from "@/components/Shell";
import { api, type Project } from "@/lib/api";

/**
 * Project list.
 *
 * No sample projects, ever. An empty account shows an empty list and says so —
 * fabricated rows in a product about provenance would undermine the only thing
 * it sells.
 */
export default function ProjectsPage() {
  return (
    <Shell>
      <ProjectList />
    </Shell>
  );
}

function ProjectList() {
  const [projects, setProjects] = useState<Project[] | null>(null);
  const [error, setError] = useState("");

  useEffect(() => {
    api
      .listProjects()
      .then(setProjects)
      .catch((e) => setError(e.message));
  }, []);

  return (
    <main className="mx-auto max-w-4xl px-6 py-10">
      <div className="flex items-baseline justify-between">
        <h1 className="text-2xl font-semibold text-neutral-100">Your projects</h1>
        <Link
          href="/projects/new"
          className="rounded bg-neutral-100 px-4 py-2 text-sm font-medium text-neutral-950
                     transition hover:bg-white"
        >
          New project
        </Link>
      </div>

      {error && (
        <p role="alert" className="mt-6 text-sm text-rose-400">
          {error}
        </p>
      )}

      {projects === null && !error && (
        <p className="mt-6 text-neutral-500">Loading…</p>
      )}

      {projects?.length === 0 && (
        <div className="mt-10 rounded-lg border border-dashed border-neutral-800 p-8 text-center">
          <p className="text-neutral-300">Nothing here yet.</p>
          <p className="mt-1 text-sm text-neutral-500">
            Start by creating a project and adding the master you intend to deliver.
          </p>
        </div>
      )}

      <ul className="mt-6 space-y-2">
        {projects?.map((p) => (
          <li key={p.id}>
            <Link
              href={`/projects/${p.id}/master`}
              className="block rounded-lg border border-neutral-800 p-4 transition
                         hover:border-neutral-700 hover:bg-neutral-900/50"
            >
              <div className="flex flex-wrap items-baseline justify-between gap-2">
                <span className="font-medium text-neutral-100">{p.title}</span>
                <span className="font-mono text-xs text-neutral-500">{p.state}</span>
              </div>
              <p className="mt-1 text-sm text-neutral-500">
                {p.project_type}
                {p.runtime_seconds
                  ? ` · ${Math.round(p.runtime_seconds / 60)} min`
                  : ""}
                {p.country_of_origin ? ` · ${p.country_of_origin}` : ""}
              </p>
            </Link>
          </li>
        ))}
      </ul>
    </main>
  );
}
