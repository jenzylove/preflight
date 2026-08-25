"use client";

import { useRouter } from "next/navigation";
import { useState } from "react";

import { Shell } from "@/components/Shell";
import { api } from "@/lib/api";

const TYPES = [
  ["feature", "Feature"],
  ["short", "Short"],
  ["documentary", "Documentary"],
  ["trailer", "Trailer"],
  ["series", "Series episode"],
  ["other", "Other"],
] as const;

export default function NewProjectPage() {
  return (
    <Shell>
      <NewProjectForm />
    </Shell>
  );
}

function NewProjectForm() {
  const router = useRouter();
  const [title, setTitle] = useState("");
  const [type, setType] = useState<string>("documentary");
  const [language, setLanguage] = useState("en");
  const [runtime, setRuntime] = useState("");
  const [country, setCountry] = useState("");
  const [error, setError] = useState("");
  const [busy, setBusy] = useState(false);

  async function submit(e: React.FormEvent) {
    e.preventDefault();
    setBusy(true);
    setError("");
    try {
      const project = await api.createProject({
        title,
        project_type: type,
        primary_language: language || undefined,
        // Runtime is entered in minutes because that is how films are
        // discussed; the API stores seconds because that is how they are
        // measured.
        runtime_seconds: runtime ? Math.round(Number(runtime) * 60) : undefined,
        country_of_origin: country ? country.toUpperCase() : undefined,
      });
      router.push(`/projects/${project.id}/master`);
    } catch (err) {
      setError(err instanceof Error ? err.message : "Could not create the project.");
      setBusy(false);
    }
  }

  const field =
    "mt-1 w-full rounded border border-neutral-800 bg-neutral-900 px-3 py-2 " +
    "text-neutral-100 focus:border-neutral-600 focus:outline-none";

  return (
    <main className="mx-auto max-w-xl px-6 py-10">
      <h1 className="text-2xl font-semibold text-neutral-100">New project</h1>
      <p className="mt-2 text-sm text-neutral-400">
        These details go into the delivery metadata and the release passport. You can
        change them until a package is built.
      </p>

      <form onSubmit={submit} className="mt-8 space-y-4">
        <label className="block">
          <span className="text-sm text-neutral-400">Title</span>
          <input
            required
            maxLength={300}
            value={title}
            onChange={(e) => setTitle(e.target.value)}
            className={field}
            placeholder="A Quiet Field"
          />
        </label>

        <label className="block">
          <span className="text-sm text-neutral-400">Type</span>
          <select
            value={type}
            onChange={(e) => setType(e.target.value)}
            className={field}
          >
            {TYPES.map(([value, label]) => (
              <option key={value} value={value}>
                {label}
              </option>
            ))}
          </select>
        </label>

        <div className="grid gap-4 sm:grid-cols-3">
          <label className="block">
            <span className="text-sm text-neutral-400">Language</span>
            <input
              value={language}
              onChange={(e) => setLanguage(e.target.value)}
              className={field}
              placeholder="en"
              maxLength={20}
            />
          </label>

          <label className="block">
            <span className="text-sm text-neutral-400">Runtime (min)</span>
            <input
              type="number"
              min={0}
              value={runtime}
              onChange={(e) => setRuntime(e.target.value)}
              className={field}
              placeholder="82"
            />
          </label>

          <label className="block">
            <span className="text-sm text-neutral-400">Country</span>
            <input
              value={country}
              onChange={(e) => setCountry(e.target.value)}
              className={field}
              placeholder="GB"
              maxLength={2}
            />
          </label>
        </div>

        {error && (
          <p role="alert" className="text-sm text-rose-400">
            {error}
          </p>
        )}

        <button
          type="submit"
          disabled={busy}
          className="rounded bg-neutral-100 px-5 py-2 font-medium text-neutral-950
                     transition hover:bg-white disabled:opacity-50"
        >
          {busy ? "Creating…" : "Create project"}
        </button>
      </form>
    </main>
  );
}
