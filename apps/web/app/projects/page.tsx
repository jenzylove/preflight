"use client";

import Link from "next/link";
import { useEffect, useState } from "react";
import type { User } from "firebase/auth";

import { PageHead, Workspace } from "@/components/workspace/Workspace";
import { STAGE, StageChip, type ProjectStage } from "@/components/Status";
import { api } from "@/lib/api";
import { watchUser } from "@/lib/auth";
import type { Project } from "@/lib/types";

/**
 * The workspace home.
 *
 * There is no sample project and no seeded history. A new account is genuinely
 * empty, because the first thing in it should be the user's own film — and
 * because a fake project in a product about not fabricating things would
 * undermine every claim the rest of the interface makes.
 *
 * Projects are grouped by what they need from the user rather than by date.
 * A producer opening this at midnight wants to know which film is waiting on
 * them, not which one they touched most recently.
 */
export default function ProjectsPage() {
  return (
    <Workspace wide>
      <Projects />
    </Workspace>
  );
}

/** Projects the user has to act on, before anything that is merely in flight. */
const NEEDS_YOU = new Set(["PREFLIGHT_COMPLETE", "DRAFT", "ASSETS_UPLOADED"]);
const IN_FLIGHT = new Set([
  "DESTINATIONS_CONFIRMED",
  "REPAIR_APPROVED",
  "PROCESSING",
]);
const DONE = new Set(["PACKAGES_READY", "DELIVERED"]);

function Projects() {
  const [projects, setProjects] = useState<Project[] | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [user, setUser] = useState<User | null>(null);

  useEffect(() => watchUser(setUser), []);

  useEffect(() => {
    api
      .listProjects()
      .then(setProjects)
      .catch((caught) =>
        setError(
          caught instanceof Error
            ? caught.message
            : "Could not load your projects.",
        ),
      );
  }, []);

  if (error) {
    return (
      <>
        <PageHead title="Projects" />
        <Problem message={error} />
      </>
    );
  }

  if (!projects) {
    return (
      <>
        <PageHead title="Projects" />
        <p className="slate text-paper-400" role="status">
          Loading your projects
        </p>
      </>
    );
  }

  if (projects.length === 0) {
    return <Empty />;
  }

  const live = projects.filter((p) => p.state !== "DELETED");
  const groups = [
    { title: "Needs you", items: live.filter((p) => NEEDS_YOU.has(p.state)) },
    { title: "In progress", items: live.filter((p) => IN_FLIGHT.has(p.state)) },
    { title: "Verified", items: live.filter((p) => DONE.has(p.state)) },
  ].filter((group) => group.items.length > 0);

  return (
    <>
      <PageHead
        eyebrow={greeting(user)}
        title="Prepare your finished films for delivery."
        actions={
          <Link
            href="/projects/new"
            className="rounded-[3px] bg-paper-000 px-4 py-2 text-sm font-medium
                       text-ink-000 transition hover:bg-white"
          >
            New delivery
          </Link>
        }
      />

      <div className="space-y-12">
        {groups.map((group) => (
          <section key={group.title}>
            <h2 className="slate mb-4 text-paper-400">{group.title}</h2>
            <ul className="grid gap-3 sm:grid-cols-2">
              {group.items.map((project) => (
                <li key={project.id}>
                  <ProjectCard project={project} />
                </li>
              ))}
            </ul>
          </section>
        ))}
      </div>
    </>
  );
}

function ProjectCard({ project }: { project: Project }) {
  const stage = STAGE[project.state as ProjectStage] ?? STAGE.DRAFT;

  return (
    <Link
      href={`/projects/${project.id}/${entryPoint(project.state)}`}
      className="group block rounded-[3px] border border-line bg-ink-100 p-5 transition
                 hover:border-line-strong focus:outline-none focus-visible:ring-2
                 focus-visible:ring-paper-000/40"
    >
      <div className="flex items-start justify-between gap-4">
        <h3 className="font-display text-lg leading-snug text-paper-000">
          {project.title}
        </h3>
        <StageChip state={project.state} />
      </div>

      <p className="mt-3 text-sm text-paper-300">{stage.next}</p>

      <dl className="mt-4 flex flex-wrap gap-x-5 gap-y-1 text-xs text-paper-400">
        <div>
          <dt className="inline">Type: </dt>
          <dd className="inline text-paper-300">{project.project_type}</dd>
        </div>
        {project.runtime_seconds != null && (
          <div>
            <dt className="inline">Runtime: </dt>
            <dd className="inline text-paper-300">
              {formatRuntime(project.runtime_seconds)}
            </dd>
          </div>
        )}
        {project.primary_language && (
          <div>
            <dt className="inline">Language: </dt>
            <dd className="inline text-paper-300">{project.primary_language}</dd>
          </div>
        )}
      </dl>
    </Link>
  );
}

function Empty() {
  return (
    <div className="mx-auto max-w-xl py-16 text-center">
      <p className="slate text-paper-400">Your workspace</p>
      <h1 className="mt-5 font-display text-display-sm leading-tight text-paper-000">
        Your first delivery starts with a finished film.
      </h1>
      <p className="mx-auto mt-5 max-w-measure text-[15px] leading-relaxed text-paper-300">
        Preflight measures your master, retrieves what each destination
        currently requires, and prepares a package for every one of them. It
        will never change your original.
      </p>

      <Link
        href="/projects/new"
        className="mt-9 inline-flex rounded-[3px] bg-paper-000 px-6 py-3 text-sm
                   font-medium text-ink-000 transition hover:bg-white"
      >
        Upload your master
      </Link>

      <ol className="mt-14 flex flex-wrap items-center justify-center gap-x-2 gap-y-2">
        {["Master", "Destinations", "Preflight", "Repair", "Verify", "Deliver"].map(
          (step, index) => (
            <li key={step} className="flex items-center gap-2">
              {index > 0 && (
                <span aria-hidden="true" className="text-paper-500">
                  →
                </span>
              )}
              <span className="slate text-paper-400">{step}</span>
            </li>
          ),
        )}
      </ol>
    </div>
  );
}

function Problem({ message }: { message: string }) {
  return (
    <div
      role="alert"
      className="rounded-[3px] border-l-2 border-stop bg-stop-bg/40 py-4 pl-4 pr-5"
    >
      <p className="text-paper-100">{message}</p>
      <p className="mt-2 text-sm text-paper-300">
        Your projects are not lost. Reload the page, and if this keeps
        happening the service may be briefly unavailable.
      </p>
    </div>
  );
}

/** Where a project should open, given how far it has got. */
function entryPoint(state: string): string {
  switch (state) {
    case "DRAFT":
      return "master";
    case "ASSETS_UPLOADED":
      return "destinations";
    case "DESTINATIONS_CONFIRMED":
      return "preflight";
    case "PREFLIGHT_COMPLETE":
    case "REPAIR_APPROVED":
    case "PROCESSING":
      return "plan";
    default:
      return "packages";
  }
}

function greeting(user: User | null): string {
  const hour = new Date().getHours();
  const part =
    hour < 12 ? "Good morning" : hour < 18 ? "Good afternoon" : "Good evening";
  const name = user?.displayName?.split(" ")[0] ?? user?.email?.split("@")[0];
  return name ? `${part}, ${name}.` : `${part}.`;
}

function formatRuntime(seconds: number): string {
  const minutes = Math.round(seconds / 60);
  if (minutes < 60) return `${minutes} min`;
  const hours = Math.floor(minutes / 60);
  return `${hours}h ${minutes % 60}m`;
}
