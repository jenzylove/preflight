"use client";

import Link from "next/link";
import { use, useCallback, useEffect, useRef, useState } from "react";

import { ProjectRail } from "@/components/workspace/Rail";
import { Workspace } from "@/components/workspace/Workspace";
import { api } from "@/lib/api";
import type { Destination, DestinationResearch, Project } from "@/lib/types";

/**
 * Choosing where the film is going.
 *
 * Two things were wrong with this screen. It led with rule pack versions,
 * retrieval dates and mandatory-rule counts, which are the vocabulary of the
 * system rather than of the person using it. And it offered exactly the
 * destinations somebody had prepared in advance, which made the claim that
 * Preflight retrieves current requirements quietly false for every festival
 * that was not one of two.
 *
 * So the question comes first - where are you sending it - and it is answered
 * by searching, not by picking from a fixed list. What was retrieved, when,
 * and from which page is all still here, one layer down, because a requirement
 * without a source is just an assertion.
 */
export default function DestinationsPage({
  params,
}: {
  params: Promise<{ projectId: string }>;
}) {
  const { projectId } = use(params);
  return (
    <Workspace wide>
      <Destinations projectId={projectId} />
    </Workspace>
  );
}

function Destinations({ projectId }: { projectId: string }) {
  const [project, setProject] = useState<Project | null>(null);
  const [all, setAll] = useState<Destination[]>([]);
  const [chosen, setChosen] = useState<Set<string>>(new Set());
  const [saving, setSaving] = useState(false);
  const [saved, setSaved] = useState(false);
  const [error, setError] = useState<string | null>(null);

  const load = useCallback(async () => {
    const [p, destinations, selection] = await Promise.all([
      api.getProject(projectId),
      api.listDestinations(),
      api
        .getSelectedDestinations(projectId)
        .catch(() => ({ selected: [] as Destination[], project_state: "" })),
    ]);
    setProject(p);
    setAll(destinations);
    setChosen(new Set(selection.selected.map((d) => d.id)));
  }, [projectId]);

  useEffect(() => {
    load().catch((caught) =>
      setError(
        caught instanceof Error ? caught.message : "Could not load destinations.",
      ),
    );
  }, [load]);

  async function save() {
    setSaving(true);
    setError(null);
    try {
      await api.setDestinations(projectId, [...chosen]);
      setSaved(true);
      await load();
    } catch (caught) {
      setError(
        caught instanceof Error ? caught.message : "That selection was not saved.",
      );
    } finally {
      setSaving(false);
    }
  }

  function toggle(id: string) {
    setSaved(false);
    setChosen((current) => {
      const next = new Set(current);
      if (next.has(id)) next.delete(id);
      else next.add(id);
      return next;
    });
  }

  if (!project) {
    return (
      <p className="slate text-paper-400" role="status">
        Loading
      </p>
    );
  }

  const available = all.filter((d) => d.available);
  // Destinations that cannot be read are not offered as if they could be.
  // They are named further down, with the reason and something to do about it.
  const needsPrivateSpec = all.filter((d) => !d.available);

  return (
    <>
      <ProjectRail project={project} />

      <div className="mb-8">
        <h2 className="font-display text-2xl text-paper-000">
          Where are you sending your film?
        </h2>
        <p className="mt-3 max-w-measure text-[15px] leading-relaxed text-paper-300">
          Search for a festival, broadcaster or platform. Preflight looks up
          what they publish about delivery today, then checks your film against
          it. Choose more than one and it will tell you where they disagree.
        </p>
      </div>

      {error && (
        <p
          role="alert"
          className="mb-6 border-l-2 border-stop bg-stop-bg/40 py-3 pl-4 text-paper-100"
        >
          {error}
        </p>
      )}

      <FindDestination
        onFound={async (destination) => {
          await load();
          setSaved(false);
          setChosen((current) => new Set(current).add(destination.id));
        }}
      />

      {available.length > 0 && (
        <div className="mt-10">
          <h3 className="text-sm font-medium text-paper-100">
            Destinations you can choose
          </h3>
          <ul className="mt-4 space-y-3">
            {available.map((destination) => (
              <li key={destination.id}>
                <Choice
                  destination={destination}
                  selected={chosen.has(destination.id)}
                  onToggle={() => toggle(destination.id)}
                />
              </li>
            ))}
          </ul>
        </div>
      )}

      <div className="mt-10 flex flex-wrap items-center gap-4">
        <button
          type="button"
          onClick={save}
          disabled={saving || chosen.size === 0}
          className="rounded-[3px] bg-paper-000 px-5 py-2.5 text-sm font-medium
                     text-ink-000 transition hover:bg-white disabled:opacity-40"
        >
          {saving ? "Saving…" : "Save selection"}
        </button>
        {saved && (
          <Link
            href={`/projects/${projectId}/preflight`}
            className="rounded-[3px] border border-line-strong px-5 py-2.5 text-sm
                       text-paper-100 transition hover:bg-ink-200"
          >
            Check my film against these
          </Link>
        )}
        {chosen.size === 0 && (
          <span className="text-sm text-paper-400">
            Choose at least one destination.
          </span>
        )}
      </div>

      {needsPrivateSpec.length > 0 && <PrivateSpecNote destinations={needsPrivateSpec} />}
    </>
  );
}

/**
 * The search box, and the wait.
 *
 * The wait is the interesting part. Retrieval is genuinely slow, and the
 * honest thing is to say what is happening rather than spin: which stage it is
 * at, then what was actually found. "Nothing found" is a first-class outcome
 * with its own explanation, because a destination that does not publish a
 * verifiable specification is common and inventing one would be the worst
 * thing this product could do.
 */
function FindDestination({
  onFound,
}: {
  onFound: (destination: Destination) => Promise<void>;
}) {
  const [query, setQuery] = useState("");
  const [job, setJob] = useState<DestinationResearch | null>(null);
  const [error, setError] = useState<string | null>(null);
  const timer = useRef<ReturnType<typeof setTimeout> | null>(null);

  useEffect(() => () => {
    if (timer.current) clearTimeout(timer.current);
  }, []);

  const running =
    job !== null && ["QUEUED", "SEARCHING", "READING", "EXTRACTING"].includes(job.state);

  const poll = useCallback(
    async (jobId: string) => {
      try {
        const next = await api.readResearch(jobId);
        setJob(next);
        if (["QUEUED", "SEARCHING", "READING", "EXTRACTING"].includes(next.state)) {
          timer.current = setTimeout(() => void poll(jobId), 2500);
        } else if (next.state === "READY" && next.destination) {
          await onFound(next.destination);
        }
      } catch {
        // A dropped poll is not a failed search. Try again.
        timer.current = setTimeout(() => void poll(jobId), 4000);
      }
    },
    [onFound],
  );

  async function start(event: React.FormEvent) {
    event.preventDefault();
    if (!query.trim()) return;
    setError(null);
    setJob(null);
    try {
      const started = await api.researchDestination(query.trim());
      setJob(started);
      timer.current = setTimeout(() => void poll(started.id), 2000);
    } catch (caught) {
      setError(
        caught instanceof Error ? caught.message : "That search could not be started.",
      );
    }
  }

  return (
    <section className="rounded-[3px] border border-line bg-ink-100 p-6">
      <h3 className="text-[15px] font-medium text-paper-000">Find a destination</h3>
      <p className="mt-1.5 max-w-measure text-sm leading-relaxed text-paper-400">
        Type the name of a festival, broadcaster or platform. Preflight reads
        their own published pages, not a stored copy.
      </p>

      {/* Stacked on a phone. Sharing a row with the button left room for
          about eleven characters, which is not enough to see what you typed. */}
      <form onSubmit={start} className="mt-4 flex flex-col gap-3 sm:flex-row">
        <label htmlFor="destination-query" className="sr-only">
          Destination name
        </label>
        <input
          id="destination-query"
          value={query}
          onChange={(event) => setQuery(event.target.value)}
          disabled={running}
          placeholder="Sundance Film Festival"
          className="w-full min-w-0 rounded-[3px] border border-line bg-ink-000 px-3.5 py-2.5 sm:flex-1
                     text-[15px] text-paper-000 outline-none placeholder:text-paper-500
                     focus:border-line-strong disabled:opacity-50"
        />
        <button
          type="submit"
          disabled={running || query.trim().length < 2}
          className="w-full shrink-0 rounded-[3px] border border-line-strong px-5 py-2.5
                     text-sm text-paper-100 transition hover:bg-ink-200
                     disabled:opacity-40 sm:w-auto"
        >
          {running ? "Searching…" : "Find requirements"}
        </button>
      </form>

      {error && (
        <p role="alert" className="mt-4 text-sm text-stop">
          {error}
        </p>
      )}

      {running && (
        <div className="mt-5 border-l-2 border-line-strong pl-4">
          <p className="text-sm text-paper-100" role="status">
            Finding current requirements with Parallel…
          </p>
          <p className="mt-1 text-sm text-paper-400">
            {job?.progress ?? "Starting"}
          </p>
          <p className="mt-2 text-xs text-paper-500">
            This usually takes a minute or two. You can leave this page open.
          </p>
        </div>
      )}

      {job?.state === "READY" && job.destination && (
        <div className="mt-5 border-l-2 border-go pl-4">
          <p className="text-sm text-paper-000">
            Found {job.official_sources} official{" "}
            {job.official_sources === 1 ? "source" : "sources"} for{" "}
            {job.destination.name}
          </p>
          <p className="mt-1 text-sm text-paper-300">
            {job.mandatory_rules} delivery{" "}
            {job.mandatory_rules === 1 ? "requirement" : "requirements"} Preflight
            can measure. It has been added below and selected for you.
          </p>
          {job.rejected_sources > 0 && (
            <p className="mt-2 text-xs text-paper-500">
              {job.rejected_sources} other {job.rejected_sources === 1 ? "page" : "pages"}{" "}
              mentioned this destination but were not published by them, so nothing
              in them can create a requirement.
            </p>
          )}
        </div>
      )}

      {job?.state === "NOTHING_FOUND" && (
        <div className="mt-5 border-l-2 border-caution pl-4">
          <p className="text-sm text-paper-000">
            We couldn&rsquo;t verify an official technical specification for this
            destination.
          </p>
          <p className="mt-1 max-w-measure text-sm leading-relaxed text-paper-300">
            {job.failure_reason}
          </p>
        </div>
      )}

      {job?.state === "FAILED" && (
        <div className="mt-5 border-l-2 border-stop pl-4">
          <p className="text-sm text-paper-000">That search did not complete.</p>
          <p className="mt-1 max-w-measure text-sm leading-relaxed text-paper-300">
            {job.failure_reason}
          </p>
        </div>
      )}
    </section>
  );
}

/** One destination, as a choice rather than as a record. */
function Choice({
  destination,
  selected,
  onToggle,
}: {
  destination: Destination;
  selected: boolean;
  onToggle: () => void;
}) {
  const retrieved = destination.sources[0]?.retrieved_at;

  return (
    <div
      className={`rounded-[3px] border p-5 transition ${
        selected ? "border-line-strong bg-ink-150" : "border-line bg-ink-100"
      }`}
    >
      <label className="flex cursor-pointer items-start gap-4">
        <input
          type="checkbox"
          checked={selected}
          onChange={onToggle}
          className="mt-1 h-4 w-4 shrink-0 accent-paper-000"
        />
        <div className="min-w-0 flex-1">
          <div className="flex flex-wrap items-baseline justify-between gap-3">
            <h4 className="font-display text-lg text-paper-000">{destination.name}</h4>
            {/* The count people care about is how much will be checked, not how
                many rows are in a table. */}
            <span className="text-sm text-paper-400">
              {destination.mandatory_rules} requirement
              {destination.mandatory_rules === 1 ? "" : "s"} checked
            </span>
          </div>
          {destination.official_domain && (
            <p className="mt-1 text-sm text-paper-400">{destination.official_domain}</p>
          )}
        </div>
      </label>

      {/* Version, digest, dates and quoted excerpts all still exist. They are
          evidence, and evidence belongs where someone can ask for it. */}
      <details className="mt-4">
        <summary className="cursor-pointer text-xs text-paper-400 transition hover:text-paper-200">
          View source details
        </summary>
        <dl className="mt-3 space-y-1 border-l border-line pl-4 text-xs text-paper-400">
          {destination.rule_pack_version != null && (
            <div>
              <dt className="inline">Requirement set: </dt>
              <dd className="inline text-paper-300">
                version {destination.rule_pack_version}
              </dd>
            </div>
          )}
          {retrieved && (
            <div>
              <dt className="inline">Retrieved: </dt>
              <dd className="inline text-paper-300">{formatDate(retrieved)}</dd>
            </div>
          )}
          <div>
            <dt className="inline">Total rules read: </dt>
            <dd className="inline text-paper-300">{destination.total_rules}</dd>
          </div>
          {destination.rule_pack_digest && (
            <div>
              <dt className="inline">Digest: </dt>
              <dd className="inline font-mono text-paper-300">
                {destination.rule_pack_digest}
              </dd>
            </div>
          )}
        </dl>

        {destination.sources.length > 0 && (
          <ul className="mt-3 space-y-2 border-l border-line pl-4">
            {destination.sources.map((source, index) => (
              <li key={index} className="text-xs">
                {source.excerpt && (
                  <p className="italic leading-relaxed text-paper-300">
                    &ldquo;{source.excerpt.slice(0, 220)}
                    {source.excerpt.length > 220 ? "…" : ""}&rdquo;
                  </p>
                )}
                {source.url && (
                  <a
                    href={source.url}
                    target="_blank"
                    rel="noreferrer noopener"
                    onClick={(event) => event.stopPropagation()}
                    className="mt-1 inline-block break-all text-accent underline underline-offset-4"
                  >
                    {source.url}
                  </a>
                )}
              </li>
            ))}
          </ul>
        )}
      </details>
    </div>
  );
}

/**
 * Destinations Preflight cannot read.
 *
 * These used to sit in the main list wearing a "not retrievable" badge, which
 * made the product look broken rather than careful. They are real, and worth
 * naming, but they are not choices - so they sit at the bottom, explained,
 * rather than among things that can actually be selected.
 */
function PrivateSpecNote({ destinations }: { destinations: Destination[] }) {
  return (
    <section className="mt-16 border-t border-line pt-6">
      <h3 className="text-sm font-medium text-paper-200">
        Destinations that need a specification from them
      </h3>
      <p className="mt-2 max-w-measure text-sm leading-relaxed text-paper-400">
        Some platforms only give their delivery specification to partners, so
        there is nothing published for Preflight to read. If you have been sent
        one, it is the document to work from — Preflight will not guess at what
        it contains.
      </p>
      <p className="mt-3 text-sm text-paper-400">
        {destinations.map((d) => d.name).join(", ")}
      </p>
    </section>
  );
}

function formatDate(value: string) {
  return new Date(value).toLocaleDateString(undefined, {
    day: "numeric",
    month: "short",
    year: "numeric",
  });
}
