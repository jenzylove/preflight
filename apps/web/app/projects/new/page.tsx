"use client";

import { useRouter } from "next/navigation";
import { useState } from "react";

import { PageHead, Workspace } from "@/components/workspace/Workspace";
import { api } from "@/lib/api";

/**
 * Starting a delivery.
 *
 * Only what the backend genuinely uses. Runtime, language and country appear
 * because destinations publish requirements about them; the synopsis appears
 * because destinations ask for one and rules are measured against its length.
 * Nothing here is collected to make the form feel substantial.
 */
export default function NewProjectPage() {
  return (
    <Workspace>
      <NewProject />
    </Workspace>
  );
}

const TYPES = [
  "documentary",
  "feature",
  "short",
  "trailer",
  "series",
  "other",
] as const;

function NewProject() {
  const router = useRouter();
  const [title, setTitle] = useState("");
  const [type, setType] = useState<string>("documentary");
  const [language, setLanguage] = useState("");
  const [country, setCountry] = useState("");
  const [runtime, setRuntime] = useState("");
  const [synopsis, setSynopsis] = useState("");
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState<string | null>(null);

  async function submit(event: React.FormEvent) {
    event.preventDefault();
    setBusy(true);
    setError(null);
    try {
      const minutes = Number.parseFloat(runtime);
      const project = await api.createProject({
        title: title.trim(),
        project_type: type,
        ...(language ? { primary_language: language.trim() } : {}),
        ...(country ? { country_of_origin: country.trim().toUpperCase() } : {}),
        ...(Number.isFinite(minutes) && minutes > 0
          ? { runtime_seconds: Math.round(minutes * 60) }
          : {}),
        ...(synopsis.trim() ? { synopsis: synopsis.trim() } : {}),
      });
      router.push(`/projects/${project.id}/master`);
    } catch (caught) {
      setError(
        caught instanceof Error ? caught.message : "That project was not created.",
      );
      setBusy(false);
    }
  }

  return (
    <>
      <PageHead
        eyebrow="New delivery"
        title="What are you delivering?"
        lede="A few details destinations actually ask for. You can change any of them later."
      />

      <form onSubmit={submit} className="max-w-xl space-y-6">
        <Field
          id="title"
          label="Title"
          value={title}
          onChange={setTitle}
          required
          autoFocus
        />

        <div>
          <label htmlFor="type" className="slate block text-paper-300">
            Type
          </label>
          <select
            id="type"
            value={type}
            onChange={(event) => setType(event.target.value)}
            className="mt-2 w-full rounded-[3px] border border-line bg-ink-100 px-3.5 py-2.5
                       text-[15px] text-paper-000 outline-none focus:border-line-strong"
          >
            {TYPES.map((option) => (
              <option key={option} value={option}>
                {option}
              </option>
            ))}
          </select>
        </div>

        <div className="grid gap-6 sm:grid-cols-3">
          <Field
            id="runtime"
            label="Runtime"
            value={runtime}
            onChange={setRuntime}
            hint="minutes"
            inputMode="decimal"
          />
          <Field
            id="language"
            label="Language"
            value={language}
            onChange={setLanguage}
            hint="en"
          />
          <Field
            id="country"
            label="Country"
            value={country}
            onChange={setCountry}
            hint="GB"
            maxLength={2}
          />
        </div>

        <div>
          <label htmlFor="synopsis" className="slate block text-paper-300">
            Synopsis
          </label>
          <textarea
            id="synopsis"
            rows={4}
            value={synopsis}
            onChange={(event) => setSynopsis(event.target.value)}
            aria-describedby="synopsis-hint"
            className="mt-2 w-full rounded-[3px] border border-line bg-ink-100 px-3.5 py-2.5
                       text-[15px] leading-relaxed text-paper-000 outline-none
                       focus:border-line-strong"
          />
          <p id="synopsis-hint" className="mt-1.5 text-xs text-paper-400">
            Some destinations publish a required length for this.
          </p>
        </div>

        {error && (
          <p
            role="alert"
            className="border-l-2 border-stop bg-stop-bg/40 py-2.5 pl-3 text-sm text-paper-100"
          >
            {error}
          </p>
        )}

        <button
          type="submit"
          disabled={busy || title.trim().length === 0}
          className="rounded-[3px] bg-paper-000 px-5 py-2.5 text-sm font-medium
                     text-ink-000 transition hover:bg-white disabled:opacity-50"
        >
          {busy ? "Creating…" : "Continue to the master"}
        </button>
      </form>
    </>
  );
}

function Field({
  id,
  label,
  value,
  onChange,
  hint,
  required,
  autoFocus,
  maxLength,
  inputMode,
}: {
  id: string;
  label: string;
  value: string;
  onChange: (value: string) => void;
  hint?: string;
  required?: boolean;
  autoFocus?: boolean;
  maxLength?: number;
  inputMode?: "text" | "decimal";
}) {
  return (
    <div>
      <label htmlFor={id} className="slate block text-paper-300">
        {label}
      </label>
      <input
        id={id}
        value={value}
        required={required}
        // eslint-disable-next-line jsx-a11y/no-autofocus
        autoFocus={autoFocus}
        maxLength={maxLength}
        inputMode={inputMode}
        placeholder={hint}
        onChange={(event) => onChange(event.target.value)}
        className="mt-2 w-full rounded-[3px] border border-line bg-ink-100 px-3.5 py-2.5
                   text-[15px] text-paper-000 outline-none placeholder:text-paper-500
                   focus:border-line-strong"
      />
    </div>
  );
}
