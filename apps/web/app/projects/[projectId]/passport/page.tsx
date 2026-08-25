"use client";

import { use, useEffect, useState } from "react";

import { Shell } from "@/components/Shell";
import { api } from "@/lib/api";

/**
 * The release passport.
 *
 * Rendered from the report the backend generates, verbatim. The point of a
 * passport is that it says the same thing everywhere it is read, so the UI does
 * not summarise it, reorder it, or drop the limitations block at the end.
 */
export default function PassportPage({
  params,
}: {
  params: Promise<{ projectId: string }>;
}) {
  const { projectId } = use(params);
  return (
    <Shell>
      <Passport projectId={projectId} />
    </Shell>
  );
}

function Passport({ projectId }: { projectId: string }) {
  const [report, setReport] = useState<string>("");
  const [meta, setMeta] = useState<{ version: number; digest: string } | null>(null);
  const [error, setError] = useState("");

  useEffect(() => {
    api
      .getPassport(projectId)
      .then((p) => {
        setReport(p.report);
        setMeta({ version: p.version, digest: p.digest });
      })
      .catch((e) => setError(e instanceof Error ? e.message : "No passport yet."));
  }, [projectId]);

  return (
    <main className="mx-auto max-w-4xl px-6 py-10">
      <h1 className="text-2xl font-semibold text-neutral-100">Release passport</h1>
      <p className="mt-2 max-w-2xl text-sm text-neutral-400">
        What was delivered, what was changed, which published requirements it was
        measured against, and what Preflight could not settle.
      </p>

      {meta && (
        <p className="mt-1 font-mono text-xs text-neutral-600">
          v{meta.version} · {meta.digest}
        </p>
      )}

      {error && <p className="mt-6 text-sm text-amber-400">{error}</p>}

      {report && (
        <pre className="mt-6 overflow-x-auto rounded-lg border border-neutral-800
                        bg-neutral-950 p-5 text-xs leading-relaxed text-neutral-200">
{report}
        </pre>
      )}
    </main>
  );
}
