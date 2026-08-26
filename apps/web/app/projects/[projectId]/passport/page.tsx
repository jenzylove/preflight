"use client";

import { use, useEffect, useState } from "react";

import { ProjectRail } from "@/components/workspace/Rail";
import { Workspace } from "@/components/workspace/Workspace";
import { api } from "@/lib/api";
import type { Passport, Project } from "@/lib/types";

/**
 * The release passport.
 *
 * This is the artifact a producer forwards to a distributor or a post house,
 * so it is laid out as a document rather than a screen: original hashes, what
 * changed, which version of whose requirements it was measured against, and
 * what remains unresolved.
 *
 * The limitations are not a footnote. A passport that hid what it could not
 * check would be more dangerous than no passport at all, because the reader
 * would stop looking.
 */
export default function PassportPage({
  params,
}: {
  params: Promise<{ projectId: string }>;
}) {
  const { projectId } = use(params);
  return (
    <Workspace>
      <PassportView projectId={projectId} />
    </Workspace>
  );
}

interface PassportBody {
  projectTitle?: string;
  issuedAt?: string;
  assets?: Array<{
    role: string;
    originalFilename: string;
    originalSha256: string;
    derivedSha256?: string | null;
    pictureHash?: string | null;
    picturePreserved?: boolean | null;
    wasModified?: boolean;
    transformations?: Array<{ operation: string; parameters?: Record<string, unknown> }>;
  }>;
  destinations?: Array<{
    destinationId: string;
    rulePackVersion: number;
    rulePackDigest: string;
    sources?: Array<{ url?: string; retrievedAt?: string }>;
    packageSha256?: string | null;
    verified: boolean;
    requirementsSatisfied?: string;
    notVerifiedBecause?: string[];
  }>;
  limitations?: string[];
  verification?: { validatorVersion?: string; toolVersions?: Record<string, string> };
  approval?: { repairPlanDigest?: string; approvedAt?: string | null };
}

function PassportView({ projectId }: { projectId: string }) {
  const [project, setProject] = useState<Project | null>(null);
  const [passport, setPassport] = useState<Passport | null>(null);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    Promise.all([api.getProject(projectId), api.getPassport(projectId)])
      .then(([p, doc]) => {
        setProject(p);
        setPassport(doc);
      })
      .catch((caught) =>
        setError(
          caught instanceof Error ? caught.message : "Could not load the passport.",
        ),
      );
  }, [projectId]);

  if (error) {
    return (
      <p role="alert" className="border-l-2 border-stop bg-stop-bg/40 py-3 pl-4 text-paper-100">
        {error}
      </p>
    );
  }
  if (!project || !passport) {
    return <p className="slate text-paper-400" role="status">Loading</p>;
  }

  const body = (passport.passport ?? {}) as PassportBody;

  return (
    <>
      <ProjectRail project={project} />

      <article className="rounded-[3px] border border-line bg-ink-100">
        <header className="border-b border-line px-7 py-6">
          <p className="slate text-paper-400">Release passport</p>
          <h2 className="mt-2 font-display text-2xl text-paper-000">
            {body.projectTitle ?? project.title}
          </h2>
          <dl className="mt-4 flex flex-wrap gap-x-8 gap-y-1 text-xs">
            <Inline label="Issued" value={formatDate(passport.issued_at)} />
            <Inline label="Version" value={String(passport.version)} />
            <Inline label="Passport" value={passport.digest} mono />
          </dl>
        </header>

        <Section title="Your original files">
          <ul className="space-y-5">
            {(body.assets ?? []).map((asset) => (
              <li key={asset.role}>
                <div className="flex flex-wrap items-baseline justify-between gap-3">
                  <span className="text-[15px] text-paper-000">
                    {asset.originalFilename}
                  </span>
                  <span className="slate text-paper-400">{asset.role}</span>
                </div>
                <dl className="mt-2 space-y-1 text-xs">
                  <Row label="sha256" value={asset.originalSha256} mono />
                  {asset.derivedSha256 && (
                    <Row label="delivered as" value={asset.derivedSha256} mono />
                  )}
                  {asset.picturePreserved === true && (
                    <Row
                      label="picture"
                      value="bit-identical through processing"
                    />
                  )}
                  {asset.wasModified === false && (
                    <Row label="changed" value="not modified" />
                  )}
                </dl>
                {(asset.transformations ?? []).length > 0 && (
                  <ul className="mt-2 space-y-0.5">
                    {asset.transformations!.map((t, index) => (
                      <li key={index} className="font-mono text-xs text-paper-300">
                        → {t.operation}
                      </li>
                    ))}
                  </ul>
                )}
              </li>
            ))}
          </ul>
        </Section>

        <Section title="Measured against">
          <ul className="space-y-6">
            {(body.destinations ?? []).map((destination) => (
              <li key={destination.destinationId}>
                <div className="flex flex-wrap items-baseline justify-between gap-3">
                  <span className="text-[15px] text-paper-000">
                    {destination.destinationId}
                  </span>
                  <span
                    className={
                      destination.verified ? "text-sm text-ok" : "text-sm text-act"
                    }
                  >
                    {destination.verified
                      ? "Meets published requirements"
                      : "Not verified"}
                  </span>
                </div>

                <dl className="mt-2 space-y-1 text-xs">
                  {destination.requirementsSatisfied && (
                    <Row
                      label="requirements satisfied"
                      value={destination.requirementsSatisfied}
                    />
                  )}
                  <Row
                    label="rule pack"
                    value={`v${destination.rulePackVersion} · ${destination.rulePackDigest}`}
                    mono
                  />
                  {destination.packageSha256 && (
                    <Row label="package" value={destination.packageSha256} mono />
                  )}
                </dl>

                {(destination.sources ?? []).length > 0 && (
                  <ul className="mt-3 space-y-1.5 border-l border-line pl-4">
                    {destination.sources!.map((source, index) => (
                      <li key={index} className="text-xs">
                        {source.url && (
                          <a
                            href={source.url}
                            target="_blank"
                            rel="noreferrer noopener"
                            className="break-all text-accent underline underline-offset-4"
                          >
                            {source.url}
                          </a>
                        )}
                        {source.retrievedAt && (
                          <span className="ml-2 text-paper-400">
                            retrieved {formatDate(source.retrievedAt)}
                          </span>
                        )}
                      </li>
                    ))}
                  </ul>
                )}

                {(destination.notVerifiedBecause ?? []).length > 0 && (
                  <ul className="mt-3 space-y-1">
                    {destination.notVerifiedBecause!.map((reason, index) => (
                      <li key={index} className="text-sm text-paper-300">
                        {reason}
                      </li>
                    ))}
                  </ul>
                )}
              </li>
            ))}
          </ul>
        </Section>

        {(body.limitations ?? []).length > 0 && (
          <Section title="Limitations">
            <ul className="space-y-2.5">
              {body.limitations!.map((limitation, index) => (
                <li
                  key={index}
                  className="border-l-2 border-line-strong pl-4 text-sm leading-relaxed
                             text-paper-200"
                >
                  {limitation}
                </li>
              ))}
            </ul>
          </Section>
        )}

        <Section title="How this was checked">
          <dl className="space-y-1 text-xs">
            <Row
              label="validator"
              value={body.verification?.validatorVersion ?? null}
              mono
            />
            {Object.entries(body.verification?.toolVersions ?? {}).map(
              ([tool, version]) => (
                <Row key={tool} label={tool} value={version} mono />
              ),
            )}
            <Row
              label="approved plan"
              value={body.approval?.repairPlanDigest ?? null}
              mono
            />
            <Row
              label="approved at"
              value={
                body.approval?.approvedAt
                  ? formatDate(body.approval.approvedAt)
                  : null
              }
            />
          </dl>
        </Section>

        <footer className="border-t border-line px-7 py-5">
          <details>
            <summary className="cursor-pointer text-xs text-paper-400 hover:text-paper-200">
              The passport as issued
            </summary>
            <pre className="mt-3 max-h-96 overflow-auto whitespace-pre-wrap rounded-[3px]
                            border border-line bg-ink-000 p-4 font-mono text-[11px]
                            leading-relaxed text-paper-300">
              {passport.report}
            </pre>
          </details>
        </footer>
      </article>
    </>
  );
}

function Section({
  title,
  children,
}: {
  title: string;
  children: React.ReactNode;
}) {
  return (
    <section className="border-b border-line px-7 py-6 last:border-0">
      <h3 className="slate mb-4 text-paper-400">{title}</h3>
      {children}
    </section>
  );
}

function Row({
  label,
  value,
  mono,
}: {
  label: string;
  value: string | null | undefined;
  mono?: boolean;
}) {
  if (!value) return null;
  return (
    <div className="flex flex-wrap items-baseline justify-between gap-x-4 border-b border-line/50 pb-1">
      <dt className="text-paper-400">{label}</dt>
      <dd className={`break-all text-right text-paper-100 ${mono ? "font-mono" : ""}`}>
        {value}
      </dd>
    </div>
  );
}

function Inline({
  label,
  value,
  mono,
}: {
  label: string;
  value: string;
  mono?: boolean;
}) {
  return (
    <div>
      <dt className="inline text-paper-400">{label}: </dt>
      <dd className={`inline text-paper-200 ${mono ? "font-mono" : ""}`}>{value}</dd>
    </div>
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
