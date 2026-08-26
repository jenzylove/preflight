"use client";

import Link from "next/link";
import { use, useCallback, useEffect, useState } from "react";

import { Working } from "@/components/Status";
import { Workspace } from "@/components/workspace/Workspace";
import { ProjectRail } from "@/components/workspace/Rail";
import { api, uploadToSignedUrl } from "@/lib/api";
import type { Asset, Project } from "@/lib/types";

/**
 * Handing Preflight the master.
 *
 * The upload goes straight from the browser to private storage using a signed
 * session the API issues for one object; the file never passes through the
 * API, which is why a feature-length master is possible at all.
 *
 * Nothing on this page is measured in the browser. Every property shown comes
 * back from the worker after it has opened the file, which is why the tool and
 * its version are recorded next to the numbers.
 */

const SLOTS = [
  {
    role: "master",
    title: "The master",
    hint: "MP4 or QuickTime. This is the file everything else is measured against.",
    accept: ".mp4,.mov,video/mp4,video/quicktime",
    required: true,
  },
  {
    role: "subtitle",
    title: "Subtitles",
    hint: "SubRip or WebVTT, as a separate file.",
    accept: ".srt,.vtt,text/vtt",
    required: false,
  },
  {
    role: "poster",
    title: "Key art",
    hint: "JPEG or PNG.",
    accept: ".jpg,.jpeg,.png,image/jpeg,image/png",
    required: false,
  },
] as const;

export default function MasterPage({
  params,
}: {
  params: Promise<{ projectId: string }>;
}) {
  const { projectId } = use(params);
  return (
    <Workspace>
      <Master projectId={projectId} />
    </Workspace>
  );
}

function Master({ projectId }: { projectId: string }) {
  const [project, setProject] = useState<Project | null>(null);
  const [assets, setAssets] = useState<Asset[]>([]);
  const [error, setError] = useState<string | null>(null);

  const refresh = useCallback(async () => {
    const [p, a] = await Promise.all([
      api.getProject(projectId),
      api.listAssets(projectId),
    ]);
    setProject(p);
    setAssets(a);
  }, [projectId]);

  useEffect(() => {
    refresh().catch((caught) =>
      setError(caught instanceof Error ? caught.message : "Could not load this project."),
    );
  }, [refresh]);

  if (error) {
    return (
      <p role="alert" className="border-l-2 border-stop bg-stop-bg/40 py-4 pl-4 text-paper-100">
        {error}
      </p>
    );
  }
  if (!project) {
    return <p className="slate text-paper-400" role="status">Loading</p>;
  }

  const master = assets.find((a) => a.role === "master");

  return (
    <>
      <ProjectRail project={project} />

      <div className="mb-10">
        <h2 className="font-display text-2xl text-paper-000">
          {master ? "Your master, measured" : "Give Preflight the master"}
        </h2>
        <p className="mt-3 max-w-measure text-[15px] leading-relaxed text-paper-300">
          {master
            ? "Everything below was read from the file itself after upload. Your original is stored unchanged and is never written to."
            : "Upload the finished film. Preflight will open it, measure what it actually is, and record a hash so you can prove the original was never altered."}
        </p>
      </div>

      <div className="space-y-4">
        {SLOTS.map((slot) => (
          <Slot
            key={slot.role}
            projectId={projectId}
            slot={slot}
            asset={assets.find((a) => a.role === slot.role)}
            onDone={refresh}
          />
        ))}
      </div>

      {master && (
        <div className="mt-10 flex justify-end">
          <Link
            href={`/projects/${projectId}/destinations`}
            className="rounded-[3px] bg-paper-000 px-5 py-2.5 text-sm font-medium
                       text-ink-000 transition hover:bg-white"
          >
            Choose destinations
          </Link>
        </div>
      )}
    </>
  );
}

type SlotSpec = (typeof SLOTS)[number];

function Slot({
  projectId,
  slot,
  asset,
  onDone,
}: {
  projectId: string;
  slot: SlotSpec;
  asset?: Asset;
  onDone: () => Promise<void>;
}) {
  const [phase, setPhase] = useState<"idle" | "sending" | "measuring">("idle");
  const [sent, setSent] = useState(0);
  const [failure, setFailure] = useState<string | null>(null);
  const [language, setLanguage] = useState("");

  async function upload(file: File) {
    setFailure(null);
    setPhase("sending");
    setSent(0);
    try {
      const intent = await api.uploadIntent(projectId, {
        role: slot.role,
        filename: file.name,
        content_type: file.type || guessType(file.name),
        byte_size: file.size,
        ...(slot.role === "subtitle" && language ? { language } : {}),
      });

      await uploadToSignedUrl(intent.upload_url, file, setSent);

      // The worker opens the file here. On a long master this is the slow
      // part, and it is honest to say what is happening rather than leave the
      // progress bar sitting at 100%.
      setPhase("measuring");
      await api.completeUpload(projectId, intent.asset_id);
      await onDone();
      setPhase("idle");
    } catch (caught) {
      setFailure(
        caught instanceof Error ? caught.message : "That upload did not complete.",
      );
      setPhase("idle");
    }
  }

  return (
    <section className="rounded-[3px] border border-line bg-ink-100 p-5">
      <div className="flex flex-wrap items-baseline justify-between gap-3">
        <div>
          <h3 className="text-[15px] font-medium text-paper-000">
            {slot.title}
            {!slot.required && (
              <span className="ml-2 text-xs font-normal text-paper-400">optional</span>
            )}
          </h3>
          <p className="mt-1 text-sm text-paper-400">{slot.hint}</p>
        </div>

        {!asset && phase === "idle" && (
          <label className="cursor-pointer rounded-[3px] border border-line-strong px-4 py-2
                            text-sm text-paper-100 transition hover:bg-ink-200">
            Choose file
            <input
              type="file"
              accept={slot.accept}
              className="sr-only"
              onChange={(event) => {
                const file = event.target.files?.[0];
                if (file) void upload(file);
              }}
            />
          </label>
        )}
      </div>

      {slot.role === "subtitle" && !asset && phase === "idle" && (
        <div className="mt-4">
          <label htmlFor="sub-lang" className="slate block text-paper-400">
            Language of these subtitles
          </label>
          <input
            id="sub-lang"
            value={language}
            onChange={(event) => setLanguage(event.target.value)}
            placeholder="en"
            className="mt-2 w-28 rounded-[3px] border border-line bg-ink-000 px-3 py-1.5
                       font-mono text-sm text-paper-000 outline-none focus:border-line-strong"
          />
          {/* A subtitle file does not record its own language, and taking the
              film's primary language as the subtitle's would be a measurement
              nobody made. So it is asked for. */}
          <p className="mt-1.5 text-xs text-paper-400">
            Subtitle files do not carry this, so Preflight cannot read it. Some
            destinations require it.
          </p>
        </div>
      )}

      {phase === "sending" && (
        <div className="mt-4">
          <div className="h-[2px] w-full overflow-hidden rounded-full bg-ink-200">
            <div
              className="h-full bg-paper-200 transition-[width] duration-200"
              style={{ width: `${Math.round(sent * 100)}%` }}
            />
          </div>
          <p className="mt-2 text-sm text-paper-300" role="status">
            Sending to private storage · {Math.round(sent * 100)}%
          </p>
        </div>
      )}

      {phase === "measuring" && (
        <div className="mt-4">
          <Working label="Opening the file and measuring it" />
        </div>
      )}

      {failure && (
        <p role="alert" className="mt-4 border-l-2 border-stop bg-stop-bg/40 py-2.5 pl-3 text-sm text-paper-100">
          {failure}
        </p>
      )}

      {asset && <Measured asset={asset} />}
    </section>
  );
}

/**
 * What the worker found.
 *
 * Grouped and labelled rather than dumped as JSON, with the raw evidence
 * available underneath for anyone who wants it. Provenance sits with the
 * values because a measurement without a tool and version behind it is just
 * an assertion.
 */
function Measured({ asset }: { asset: Asset }) {
  const properties = asset.measured_properties ?? {};
  const groups = Object.entries(properties).filter(
    ([, value]) => value && typeof value === "object",
  ) as [string, Record<string, unknown>][];

  const flat = Object.entries(properties).filter(
    ([, value]) => !value || typeof value !== "object",
  );

  return (
    <div className="mt-5 border-t border-line pt-5">
      <div className="flex flex-wrap items-baseline gap-x-6 gap-y-1">
        <p className="text-sm text-paper-100">{asset.original_filename}</p>
        <p className="text-xs text-paper-400">{formatBytes(asset.byte_size)}</p>
      </div>

      {groups.map(([groupName, values]) => (
        <div key={groupName} className="mt-4">
          <h4 className="slate mb-2 text-paper-400">{groupName}</h4>
          <dl className="grid gap-x-8 gap-y-1.5 sm:grid-cols-2">
            {Object.entries(values)
              .filter(([key]) => !key.startsWith("_"))
              .map(([key, value]) => (
                <Row key={key} label={key} value={value} />
              ))}
          </dl>
        </div>
      ))}

      {flat.length > 0 && (
        <dl className="mt-4 grid gap-x-8 gap-y-1.5 sm:grid-cols-2">
          {flat
            .filter(([key]) => !key.startsWith("_"))
            .map(([key, value]) => (
              <Row key={key} label={key} value={value} />
            ))}
        </dl>
      )}

      <details className="mt-5">
        <summary className="cursor-pointer text-xs text-paper-400 hover:text-paper-200">
          Provenance
        </summary>
        <dl className="mt-3 space-y-1.5 border-l border-line pl-4">
          <Row label="sha256" value={asset.sha256} mono />
          <Row label="measured by" value={asset.inspector} />
          <Row label="tool version" value={asset.inspector_version} mono />
          <Row label="custody" value={asset.custody_state} />
          <Row label="original is immutable" value={asset.immutable} />
        </dl>
      </details>
    </div>
  );
}

function Row({
  label,
  value,
  mono,
}: {
  label: string;
  value: unknown;
  mono?: boolean;
}) {
  if (value === null || value === undefined || value === "") return null;
  return (
    <div className="flex items-baseline justify-between gap-4 border-b border-line/60 pb-1">
      <dt className="text-xs text-paper-400">{humanise(label)}</dt>
      <dd
        className={`text-right text-[13px] text-paper-100 ${
          mono || typeof value === "number" ? "font-mono" : ""
        }`}
      >
        {String(value)}
      </dd>
    </div>
  );
}

/** camelCase property names are for the wire, not for a person reading a page. */
function humanise(key: string): string {
  return key
    .replace(/([A-Z])/g, " $1")
    .replace(/^./, (c) => c.toUpperCase())
    .replace(/ Px$/, " (px)")
    .replace(/ Bps$/, " (bps)")
    .replace(/ Lufs$/, " (LUFS)")
    .replace(/ Dbtp$/, " (dBTP)")
    .replace(/ Hz$/, " (Hz)")
    .replace(/ Lu$/, " (LU)")
    .trim();
}

function formatBytes(bytes: number): string {
  if (bytes < 1024 * 1024) return `${(bytes / 1024).toFixed(0)} KB`;
  if (bytes < 1024 * 1024 * 1024) return `${(bytes / 1024 / 1024).toFixed(1)} MB`;
  return `${(bytes / 1024 / 1024 / 1024).toFixed(2)} GB`;
}

function guessType(filename: string): string {
  const ext = filename.split(".").pop()?.toLowerCase();
  switch (ext) {
    case "mov":
      return "video/quicktime";
    case "mp4":
      return "video/mp4";
    case "vtt":
      return "text/vtt";
    case "srt":
      return "application/x-subrip";
    case "png":
      return "image/png";
    default:
      return "image/jpeg";
  }
}
