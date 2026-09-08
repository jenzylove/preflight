"use client";

import { useRouter } from "next/navigation";
import { useState } from "react";

import { PageHead, Workspace } from "@/components/workspace/Workspace";
import { api } from "@/lib/api";
import { COUNTRIES, LANGUAGES, PROJECT_TYPES } from "@/lib/language";

/**
 * Starting a delivery.
 *
 * This is the first screen after signing up, so it decides whether Preflight
 * reads as a tool for filmmakers or as a form for engineers. Two questions are
 * asked outright - what is it called, and what kind of thing is it - because
 * those are the only two the system genuinely needs to create the delivery.
 *
 * Everything else a festival might ask about is real, but it is not needed
 * yet, and asking for it here made the first screen feel like a database
 * record. It waits under a disclosure, in plain words, with the codes hidden:
 * nobody should have to know that Nigeria is NG or that English is en.
 *
 * Runtime is not asked for at all. It is measured from the film on upload.
 */
export default function NewProjectPage() {
  return (
    <Workspace>
      <NewProject />
    </Workspace>
  );
}

function NewProject() {
  const router = useRouter();
  const [title, setTitle] = useState("");
  const [type, setType] = useState<string>("feature");
  const [language, setLanguage] = useState("");
  const [country, setCountry] = useState("");
  const [synopsis, setSynopsis] = useState("");
  const [showMore, setShowMore] = useState(false);
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState<string | null>(null);

  const chosenType = PROJECT_TYPES.find((t) => t.value === type);

  async function submit(event: React.FormEvent) {
    event.preventDefault();
    setBusy(true);
    setError(null);
    try {
      const project = await api.createProject({
        title: title.trim(),
        project_type: type,
        ...(language ? { primary_language: language } : {}),
        ...(country ? { country_of_origin: country } : {}),
        ...(synopsis.trim() ? { synopsis: synopsis.trim() } : {}),
      });
      router.push(`/projects/${project.id}/master`);
    } catch (caught) {
      setError(
        caught instanceof Error ? caught.message : "That delivery was not created.",
      );
      setBusy(false);
    }
  }

  return (
    <>
      <PageHead
        eyebrow="New delivery"
        title="What are you sending?"
        lede="Just enough to get started. You can add the rest later, and Preflight measures the film itself once you upload it."
      />

      <form onSubmit={submit} className="max-w-xl space-y-8">
        <div>
          <label htmlFor="title" className="block text-sm font-medium text-paper-100">
            What is your film called?
          </label>
          <input
            id="title"
            value={title}
            onChange={(event) => setTitle(event.target.value)}
            required
            autoFocus
            placeholder="A Quiet Field"
            className="mt-2 w-full rounded-[3px] border border-line bg-ink-100 px-3.5 py-2.5
                       text-[15px] text-paper-000 outline-none placeholder:text-paper-500
                       focus:border-line-strong"
          />
        </div>

        <div>
          <label htmlFor="type" className="block text-sm font-medium text-paper-100">
            What kind of film is it?
          </label>
          <select
            id="type"
            value={type}
            onChange={(event) => setType(event.target.value)}
            aria-describedby="type-hint"
            className="mt-2 w-full rounded-[3px] border border-line bg-ink-100 px-3.5 py-2.5
                       text-[15px] text-paper-000 outline-none focus:border-line-strong"
          >
            {PROJECT_TYPES.map((option) => (
              <option key={option.value} value={option.value}>
                {option.label}
              </option>
            ))}
          </select>
          {/* The taxonomy has overlapping names, so the chosen one explains
              itself rather than leaving someone to guess whether a
              feature-length documentary is a documentary or a feature. */}
          <p id="type-hint" className="mt-2 text-sm leading-relaxed text-paper-400">
            {chosenType?.hint}
          </p>
        </div>

        <div className="border-t border-line pt-6">
          <button
            type="button"
            onClick={() => setShowMore((open) => !open)}
            aria-expanded={showMore}
            className="flex items-center gap-2 text-sm text-paper-200 transition hover:text-paper-000"
          >
            <svg
              aria-hidden="true"
              viewBox="0 0 12 12"
              className={`h-3 w-3 transition ${showMore ? "rotate-90" : ""}`}
            >
              <path d="M4.5 2.5L8 6l-3.5 3.5" fill="none" stroke="currentColor"
                    strokeWidth="1.4" strokeLinecap="round" strokeLinejoin="round" />
            </svg>
            Additional delivery details
            <span className="text-paper-400">optional</span>
          </button>

          <p className="mt-2 text-sm leading-relaxed text-paper-400">
            Some festivals publish requirements about these. You can fill them in
            now or come back to them.
          </p>

          {showMore && (
            <div className="mt-6 space-y-6">
              <div className="grid gap-6 sm:grid-cols-2">
                <div>
                  <label
                    htmlFor="language"
                    className="block text-sm font-medium text-paper-100"
                  >
                    Main language of the film
                  </label>
                  <select
                    id="language"
                    value={language}
                    onChange={(event) => setLanguage(event.target.value)}
                    className="mt-2 w-full rounded-[3px] border border-line bg-ink-100
                               px-3.5 py-2.5 text-[15px] text-paper-000 outline-none
                               focus:border-line-strong"
                  >
                    <option value="">Not saying yet</option>
                    {LANGUAGES.map((option) => (
                      <option key={option.code} value={option.code}>
                        {option.name}
                      </option>
                    ))}
                  </select>
                </div>

                <div>
                  <label
                    htmlFor="country"
                    className="block text-sm font-medium text-paper-100"
                  >
                    Country of origin
                  </label>
                  <select
                    id="country"
                    value={country}
                    onChange={(event) => setCountry(event.target.value)}
                    className="mt-2 w-full rounded-[3px] border border-line bg-ink-100
                               px-3.5 py-2.5 text-[15px] text-paper-000 outline-none
                               focus:border-line-strong"
                  >
                    <option value="">Not saying yet</option>
                    {COUNTRIES.map((option) => (
                      <option key={option.code} value={option.code}>
                        {option.name}
                      </option>
                    ))}
                  </select>
                </div>
              </div>

              <div>
                <label
                  htmlFor="synopsis"
                  className="block text-sm font-medium text-paper-100"
                >
                  Short summary of your film{" "}
                  <span className="font-normal text-paper-400">optional</span>
                </label>
                <textarea
                  id="synopsis"
                  rows={4}
                  value={synopsis}
                  onChange={(event) => setSynopsis(event.target.value)}
                  aria-describedby="synopsis-hint"
                  placeholder="A field before anyone arrives, and the sound that builds and falls away across a single afternoon."
                  className="mt-2 w-full rounded-[3px] border border-line bg-ink-100 px-3.5
                             py-2.5 text-[15px] leading-relaxed text-paper-000 outline-none
                             placeholder:text-paper-500 focus:border-line-strong"
                />
                <p id="synopsis-hint" className="mt-2 text-sm leading-relaxed text-paper-400">
                  A few sentences describing the film. Some festivals ask for one
                  of a particular length, so Preflight can check it against what
                  they publish.
                </p>
              </div>
            </div>
          )}
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
          {busy ? "Creating…" : "Continue"}
        </button>
      </form>
    </>
  );
}
