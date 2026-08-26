"use client";

import Link from "next/link";
import { usePathname } from "next/navigation";

import type { Project } from "@/lib/types";
import { STAGE, type ProjectStage } from "@/components/Status";

/**
 * Where this project has got to, and where it goes next.
 *
 * The steps are the product's actual sequence, not a progress bar. A film does
 * not move through delivery as a percentage, and a bar that invented one would
 * be the first thing in the interface a user could catch being made up.
 *
 * Steps behind the current one are reachable, because going back to look at
 * the measurements or the requirements is normal. Steps ahead are not links:
 * there is nothing there yet.
 */

const STEPS = [
  { key: "master", label: "Master", reachedAt: 0 },
  { key: "destinations", label: "Destinations", reachedAt: 1 },
  { key: "preflight", label: "Preflight", reachedAt: 2 },
  { key: "plan", label: "Repair", reachedAt: 3 },
  { key: "packages", label: "Packages", reachedAt: 5 },
  { key: "passport", label: "Passport", reachedAt: 5 },
] as const;

/** How far a project's backend state carries it along that sequence. */
const REACH: Record<string, number> = {
  DRAFT: 0,
  ASSETS_UPLOADED: 1,
  DESTINATIONS_CONFIRMED: 2,
  PREFLIGHT_COMPLETE: 3,
  REPAIR_APPROVED: 4,
  PROCESSING: 4,
  PACKAGES_READY: 5,
  DELIVERED: 5,
  DELETION_PENDING: 0,
  DELETED: 0,
};

export function ProjectRail({ project }: { project: Project }) {
  const pathname = usePathname() ?? "";
  const reach = REACH[project.state] ?? 0;
  const stage = STAGE[project.state as ProjectStage] ?? STAGE.DRAFT;

  return (
    <div className="mb-10 border-b border-line pb-6">
      <div className="flex flex-wrap items-baseline gap-x-4 gap-y-2">
        <Link
          href="/projects"
          className="slate text-paper-400 transition hover:text-paper-200"
        >
          Projects
        </Link>
        <span aria-hidden="true" className="text-paper-500">
          /
        </span>
        <h1 className="font-display text-2xl leading-none text-paper-000">
          {project.title}
        </h1>
      </div>

      <nav aria-label="Delivery steps" className="mt-5">
        <ol className="flex flex-wrap items-center gap-x-1 gap-y-2">
          {STEPS.map((step) => {
            const href = `/projects/${project.id}/${step.key}`;
            const active = pathname.endsWith(`/${step.key}`);
            const reached = reach >= step.reachedAt;

            const className = `rounded-[3px] px-2.5 py-1 text-[13px] transition ${
              active
                ? "bg-ink-200 text-paper-000"
                : reached
                  ? "text-paper-300 hover:text-paper-000"
                  : "text-paper-500"
            }`;

            return (
              <li key={step.key} className="flex items-center">
                {reached ? (
                  <Link
                    href={href}
                    aria-current={active ? "step" : undefined}
                    className={className}
                  >
                    {step.label}
                  </Link>
                ) : (
                  // Not a link, and said so to assistive technology rather than
                  // just greyed out.
                  <span className={className} aria-disabled="true">
                    {step.label}
                  </span>
                )}
              </li>
            );
          })}
        </ol>
      </nav>

      {stage.next && (
        <p className="mt-4 text-sm text-paper-300">
          <span className="text-paper-400">Next:</span> {stage.next}
        </p>
      )}
    </div>
  );
}
