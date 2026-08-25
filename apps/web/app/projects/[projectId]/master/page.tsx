"use client";

import { use, useCallback, useEffect, useState } from "react";

import { Shell } from "@/components/Shell";
import { api, uploadToSignedUrl, type Asset } from "@/lib/api";

/**
 * Master assets.
 *
 * Files go straight from the browser to private storage using a resumable
 * session the API issues for one object. They never pass through the API, and
 * the browser never learns the bucket path.
 *
 * Nothing on this page is reported until the *server* has measured it. The
 * client's opinion of what it uploaded is not evidence.
 */

const ROLES = [
  {
    role: "master",
    label: "Master",
    accept: "video/mp4,video/quicktime",
    hint: "MP4 or MOV. This file is never modified — repairs write new files.",
  },
  {
    role: "subtitle",
    label: "Subtitles",
    accept: ".srt,.vtt,text/vtt,application/x-subrip,text/plain",
    hint: "SubRip or WebVTT sidecar.",
  },
  {
    role: "poster",
    label: "Poster",
    accept: "image/jpeg,image/png",
    hint: "JPEG or PNG key art.",
  },
] as const;

export default function MasterPage({
  params,
}: {
  params: Promise<{ projectId: string }>;
}) {
  const { projectId } = use(params);
  return (
    <Shell>
      <MasterAssets projectId={projectId} />
    </Shell>
  );
}

function MasterAssets({ projectId }: { projectId: string }) {
  const [assets, setAssets] = useState<Asset[]>([]);
  const [error, setError] = useState("");

  const refresh = useCallback(
    () => api.listAssets(projectId).then(setAssets).catch(() => {}),
    [projectId],
  );

  useEffect(() => {
    refresh();
  }, [refresh]);

  const byRole = Object.fromEntries(assets.map((a) => [a.role, a]));

  return (
    <main className="mx-auto max-w-3xl px-6 py-10">
      <h1 className="text-2xl font-semibold text-neutral-100">Your master</h1>
      <p className="mt-2 text-sm text-neutral-400">
        Add the files you intend to deliver. Preflight measures each one with
        ffprobe, ffmpeg and Pillow after it arrives, and records the tool version
        alongside every value.
      </p>

      {error && (
        <p role="alert" className="mt-4 text-sm text-rose-400">
          {error}
        </p>
      )}

      <div className="mt-8 space-y-4">
        {ROLES.map((spec) => (
          <AssetSlot
            key={spec.role}
            projectId={projectId}
            spec={spec}
            asset={byRole[spec.role]}
            onDone={refresh}
            onError={setError}
          />
        ))}
      </div>

      {byRole.master?.sha256 && (
        <a
          href={`/projects/${projectId}/destinations`}
          className="mt-8 inline-block rounded bg-neutral-100 px-5 py-2 font-medium
                     text-neutral-950 transition hover:bg-white"
        >
          Choose destinations
        </a>
      )}
    </main>
  );
}

function AssetSlot({
  projectId,
  spec,
  asset,
  onDone,
  onError,
}: {
  projectId: string;
  spec: (typeof ROLES)[number];
  asset?: Asset;
  onDone: () => void;
  onError: (m: string) => void;
}) {
  const [progress, setProgress] = useState<number | null>(null);
  const [measuring, setMeasuring] = useState(false);

  async function handle(file: File) {
    onError("");
    setProgress(0);
    try {
      const intent = await api.uploadIntent(projectId, {
        role: spec.role,
        filename: file.name,
        content_type: file.type || "application/octet-stream",
        byte_size: file.size,
      });
      await uploadToSignedUrl(intent.upload_url, file, setProgress);
      setProgress(null);
      setMeasuring(true);
      await api.completeUpload(projectId, intent.asset_id);
      onDone();
    } catch (err) {
      onError(err instanceof Error ? err.message : "Upload failed.");
    } finally {
      setProgress(null);
      setMeasuring(false);
    }
  }

  return (
    <section className="rounded-lg border border-neutral-800 p-4">
      <div className="flex flex-wrap items-baseline justify-between gap-2">
        <h2 className="font-medium text-neutral-100">{spec.label}</h2>
        {asset?.sha256 && (
          <span className="text-xs text-emerald-400">Measured</span>
        )}
      </div>
      <p className="mt-1 text-sm text-neutral-500">{spec.hint}</p>

      {!asset && progress === null && !measuring && (
        <input
          type="file"
          accept={spec.accept}
          onChange={(e) => {
            const f = e.target.files?.[0];
            if (f) handle(f);
          }}
          className="mt-3 block w-full text-sm text-neutral-400
                     file:mr-3 file:rounded file:border-0 file:bg-neutral-800
                     file:px-3 file:py-1.5 file:text-neutral-200"
        />
      )}

      {progress !== null && (
        <div className="mt-3">
          <div className="h-1.5 overflow-hidden rounded bg-neutral-800">
            <div
              className="h-full bg-sky-500 transition-all"
              style={{ width: `${Math.round(progress * 100)}%` }}
            />
          </div>
          <p className="mt-1 text-xs text-neutral-500">
            Uploading directly to private storage — {Math.round(progress * 100)}%
          </p>
        </div>
      )}

      {measuring && (
        <p className="mt-3 text-sm text-sky-400">
          Measuring the file the server received…
        </p>
      )}

      {asset && <Measured asset={asset} />}
    </section>
  );
}

function Measured({ asset }: { asset: Asset }) {
  const props = asset.measured_properties;
  const flat: [string, unknown][] = [];

  if (props) {
    for (const [k, v] of Object.entries(props)) {
      if (v && typeof v === "object" && !Array.isArray(v)) {
        for (const [k2, v2] of Object.entries(v as Record<string, unknown>)) {
          if (v2 !== null && !k2.startsWith("_")) flat.push([`${k}.${k2}`, v2]);
        }
      } else if (v !== null) {
        flat.push([k, v]);
      }
    }
  }

  return (
    <div className="mt-3 space-y-2 text-sm">
      <p className="text-neutral-300">{asset.original_filename}</p>

      {asset.sha256 && (
        <p className="break-all font-mono text-xs text-neutral-500">
          sha256 {asset.sha256}
        </p>
      )}

      {asset.inspector && (
        <p className="text-xs text-neutral-500">
          Measured by {asset.inspector} {asset.inspector_version}
        </p>
      )}

      {flat.length > 0 && (
        <details>
          <summary className="cursor-pointer text-xs text-neutral-500 hover:text-neutral-300">
            What Preflight measured ({flat.length} properties)
          </summary>
          <dl className="mt-2 grid grid-cols-2 gap-x-4 gap-y-1 text-xs">
            {flat.map(([k, v]) => (
              <div key={k} className="contents">
                <dt className="truncate font-mono text-neutral-500">{k}</dt>
                <dd className="text-neutral-300">{String(v)}</dd>
              </div>
            ))}
          </dl>
        </details>
      )}
    </div>
  );
}
