"use client";

import Link from "next/link";
import { use, useCallback, useEffect, useState } from "react";

import { StatusChip, Working } from "@/components/Status";
import { ProjectRail } from "@/components/workspace/Rail";
import { Workspace } from "@/components/workspace/Workspace";
import { api } from "@/lib/api";
import type { Destination, Project } from "@/lib/types";

/**
 * Choosing where the film is going.
 *
 * The list comes from the API, which reports which destinations Preflight can
 * actually read. That distinction is the product rather than a caveat: a
 * destination whose requirements sit behind a partner login, or are rendered
 * by script, cannot be retrieved, and saying so here is more useful than
 * offering it and failing later.
 *
 * The source and its retrieval date are shown on the destination itself,
 * because "current requirements" is a claim that needs a date attached.
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

  if (!project) {
    return <p className="slate text-paper-400" role="status">Loading</p>;
  }

  const available = all.filter((d) => d.available);
  const unavailable = all.filter((d) => !d.available);

  return (
    <>
      <ProjectRail project={project} />

      <div className="mb-8">
        <h2 className="font-display text-2xl text-paper-000">
          Where is this film going?
        </h2>
        <p className="mt-3 max-w-measure text-[15px] leading-relaxed text-paper-300">
          Preflight retrieves each destination&rsquo;s current published
          requirements and measures your film against them. Choose more than
          one and it will tell you where they disagree.
        </p>
      </div>

      {error && (
        <p role="alert" className="mb-6 border-l-2 border-stop bg-stop-bg/40 py-3 pl-4 text-paper-100">
          {error}
        </p>
      )}

      <ul className="space-y-3">
        {available.map((destination) => (
          <li key={destination.id}>
            <Choice
              destination={destination}
              selected={chosen.has(destination.id)}
              onToggle={() => {
                setSaved(false);
                setChosen((current) => {
                  const next = new Set(current);
                  if (next.has(destination.id)) next.delete(destination.id);
                  else next.add(destination.id);
                  return next;
                });
              }}
            />
          </li>
        ))}
      </ul>

      {unavailable.length > 0 && (
        <section className="mt-10">
          <h3 className="slate mb-1 text-paper-400">
            Preflight cannot read these
          </h3>
          <p className="mb-4 max-w-measure text-sm text-paper-400">
            Their requirements are real, but not retrievable. Offering them and
            failing later would be worse than saying so now.
          </p>
          <ul className="space-y-2">
            {unavailable.map((destination) => (
              <li
                key={destination.id}
                className="rounded-[3px] border border-line bg-ink-100 px-4 py-3"
              >
                <div className="flex flex-wrap items-baseline justify-between gap-3">
                  <span className="text-[15px] text-paper-200">
                    {destination.name}
                  </span>
                  <StatusChip tone="idle">Not retrievable</StatusChip>
                </div>
                {destination.unavailable_reason && (
                  <p className="mt-1.5 text-sm text-paper-400">
                    {destination.unavailable_reason}
                  </p>
                )}
              </li>
            ))}
          </ul>
        </section>
      )}

      <div className="mt-10 flex flex-wrap items-center justify-end gap-4">
        {saving && <Working label="Saving your selection" />}
        {saved && !saving && (
          <span className="text-sm text-paper-300">Selection saved.</span>
        )}
        <button
          type="button"
          onClick={save}
          disabled={saving || chosen.size === 0}
          className="rounded-[3px] border border-line-strong px-4 py-2 text-sm
                     text-paper-100 transition hover:bg-ink-200 disabled:opacity-40"
        >
          Save selection
        </button>
        {saved && (
          <Link
            href={`/projects/${projectId}/preflight`}
            className="rounded-[3px] bg-paper-000 px-5 py-2.5 text-sm font-medium
                       text-ink-000 transition hover:bg-white"
          >
            Run preflight
          </Link>
        )}
      </div>
    </>
  );
}

function Choice({
  destination,
  selected,
  onToggle,
}: {
  destination: Destination;
  selected: boolean;
  onToggle: () => void;
}) {
  const retrieved = destination.sources.find((s) => s.retrieved_at)?.retrieved_at;

  return (
    <label
      className={`block cursor-pointer rounded-[3px] border p-5 transition ${
        selected
          ? "border-line-strong bg-ink-150"
          : "border-line bg-ink-100 hover:border-line-strong"
      }`}
    >
      <div className="flex items-start gap-4">
        <input
          type="checkbox"
          checked={selected}
          onChange={onToggle}
          className="mt-1 h-4 w-4 shrink-0 accent-paper-000"
        />
        <div className="min-w-0 flex-1">
          <div className="flex flex-wrap items-baseline justify-between gap-3">
            <h3 className="font-display text-lg text-paper-000">
              {destination.name}
            </h3>
            <span className="text-xs text-paper-400">
              {destination.mandatory_rules} mandatory requirement
              {destination.mandatory_rules === 1 ? "" : "s"}
            </span>
          </div>

          {destination.official_domain && (
            <p className="mt-1 font-mono text-xs text-paper-400">
              {destination.official_domain}
            </p>
          )}

          <dl className="mt-3 flex flex-wrap gap-x-6 gap-y-1 text-xs text-paper-400">
            {destination.rule_pack_version != null && (
              <div>
                <dt className="inline">Rule pack: </dt>
                <dd className="inline text-paper-300">
                  v{destination.rule_pack_version}
                </dd>
              </div>
            )}
            {retrieved && (
              <div>
                <dt className="inline">Retrieved: </dt>
                <dd className="inline text-paper-300">{formatDate(retrieved)}</dd>
              </div>
            )}
          </dl>

          {destination.sources.length > 0 && (
            <details className="mt-3">
              <summary className="cursor-pointer text-xs text-paper-400 hover:text-paper-200">
                Where these requirements come from
              </summary>
              <ul className="mt-2 space-y-2 border-l border-line pl-4">
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
            </details>
          )}
        </div>
      </div>
    </label>
  );
}

function formatDate(iso: string): string {
  const date = new Date(iso);
  return Number.isNaN(date.getTime())
    ? iso
    : date.toLocaleDateString(undefined, {
        year: "numeric",
        month: "short",
        day: "numeric",
      });
}
