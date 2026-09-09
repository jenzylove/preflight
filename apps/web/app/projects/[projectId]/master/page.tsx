"use client";

import Link from "next/link";
import { use, useCallback, useEffect, useState } from "react";

import { Working } from "@/components/Status";
import { Workspace } from "@/components/workspace/Workspace";
import { ProjectRail } from "@/components/workspace/Rail";
import { api, uploadToSignedUrl } from "@/lib/api";
import type { UploadProgress } from "@/lib/api";
import { codecName, formatDuration, resolutionName } from "@/lib/language";
import type { Asset, Project } from "@/lib/types";

/**
 * Handing Preflight the film.
 *
 * The upload goes straight from the browser to private storage using a signed
 * session the API issues for one object; the file never passes through the
 * API, which is why a feature-length film is possible at all.
 *
 * Nothing here is measured in the browser. Every property comes back from the
 * worker after it opened the file, which is why the tool and its version are
 * recorded beside the numbers.
 *
 * What changed on this screen is who it is written for. It used to greet
 * someone who had just uploaded their film with two dozen rows of colour
 * matrices, bitrates and hashes, and no visible next step. The measurements are
 * the product and they are all still here — they are simply no longer the
 * first thing between a person and the thing they came to do.
 */

const SLOTS = [
  {
    role: "master",
    title: "Your finished film",
    hint: "The final cut, as an MP4 or QuickTime file. Everything else is checked against this.",
    accept: ".mp4,.mov,video/mp4,video/quicktime",
    required: true,
  },
  {
    role: "subtitle",
    title: "Subtitle file",
    hint: "A .srt or .vtt file. Many festivals require subtitles for films not in their own language.",
    accept: ".srt,.vtt,text/vtt",
    required: false,
  },
  {
    role: "poster",
    title: "Poster or cover image",
    hint: "A JPEG or PNG still. Festivals and platforms often ask for one alongside the film.",
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
      setError(
        caught instanceof Error ? caught.message : "Could not load this project.",
      ),
    );
  }, [refresh]);

  if (error) {
    return (
      <p
        role="alert"
        className="border-l-2 border-stop bg-stop-bg/40 py-4 pl-4 text-paper-100"
      >
        {error}
      </p>
    );
  }
  if (!project) {
    return (
      <p className="slate text-paper-400" role="status">
        Loading
      </p>
    );
  }

  // A replacement is a new immutable asset. The newest one is the active
  // input used by the next check; the earlier master remains preserved.
  const master = [...assets].reverse().find((a) => a.role === "master");
  const extras = SLOTS.filter((s) => !s.required);

  return (
    <>
      <ProjectRail project={project} />

      {!master && (
        <div className="mb-10">
          <h2 className="font-display text-2xl text-paper-000">
            Upload your finished film
          </h2>
          <p className="mt-3 max-w-measure text-[15px] leading-relaxed text-paper-300">
            Preflight opens the file and measures what it actually is, then
            records a fingerprint so you can prove your original was never
            altered. Your film is stored privately and is never changed.
          </p>
        </div>
      )}

      <Slot
        projectId={projectId}
        slot={SLOTS[0]}
        asset={master}
        onDone={refresh}
        prominent
      />

      {master && (
        <>
          <div className="mt-8 flex flex-wrap items-center justify-between gap-4">
            <p className="text-sm text-paper-400">
              That is everything Preflight needs to start checking.
            </p>
            <Link
              href={`/projects/${projectId}/destinations`}
              className="rounded-[3px] bg-paper-000 px-5 py-2.5 text-sm font-medium
                         text-ink-000 transition hover:bg-white"
            >
              Continue to destinations
            </Link>
          </div>

          {/* Secondary by construction: they only appear once the film is in,
              and they sit under a quieter heading. Someone who ignores this
              section entirely still has a working delivery. */}
          <section className="mt-14 border-t border-line pt-8">
            <h3 className="text-sm font-medium text-paper-100">
              Anything else to send with it?
            </h3>
            <p className="mt-2 max-w-measure text-sm leading-relaxed text-paper-400">
              Optional. Add these if you have them and Preflight will check them
              too — some destinations publish requirements about subtitles and
              artwork, and it can only check what it has been given.
            </p>
            <div className="mt-5 space-y-4">
              {extras.map((slot) => (
                <Slot
                  key={slot.role}
                  projectId={projectId}
                  slot={slot}
    asset={[...assets].reverse().find((a) => a.role === slot.role)}
                  onDone={refresh}
                />
              ))}
            </div>
          </section>
        </>
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
  prominent = false,
}: {
  projectId: string;
  slot: SlotSpec;
  asset?: Asset;
  onDone: () => Promise<void>;
  prominent?: boolean;
}) {
  const [phase, setPhase] = useState<"idle" | "sending" | "measuring">("idle");
  const [progress, setProgress] = useState<UploadProgress | null>(null);
  const [failure, setFailure] = useState<string | null>(null);
  const [language, setLanguage] = useState("");
  // Kept so an interrupted upload can be continued into the same object and
  // the same asset row. Starting again from the intent would leave an orphan.
  const [pending, setPending] = useState<
    { file: File; url: string; assetId: string } | null
  >(null);

  async function send(file: File, url: string, assetId: string) {
    setFailure(null);
    setPhase("sending");
    try {
      await uploadToSignedUrl(url, file, setProgress);
      setPhase("measuring");
      await api.completeUpload(projectId, assetId);
      setPending(null);
      setProgress(null);
      await onDone();
      setPhase("idle");
    } catch (caught) {
      // The session and the asset survive, so this offers continuing rather
      // than starting over.
      setPending({ file, url, assetId });
      setFailure(
        caught instanceof Error
          ? caught.message
          : "That upload did not finish.",
      );
      setPhase("idle");
    }
  }

  async function upload(file: File) {
    setFailure(null);
    setPhase("sending");
    setProgress(null);
    try {
      const intent = await api.uploadIntent(projectId, {
        role: slot.role,
        filename: file.name,
        content_type: file.type || guessType(file.name),
        byte_size: file.size,
        ...(slot.role === "subtitle" && language ? { language } : {}),
      });
      await send(file, intent.upload_url, intent.asset_id);
    } catch (caught) {
      setFailure(
        caught instanceof Error ? caught.message : "That upload could not start.",
      );
      setPhase("idle");
    }
  }

  return (
    <section
      id={`${slot.role}-upload`}
      className={`rounded-[3px] border bg-ink-100 ${
        prominent && !asset ? "border-line-strong p-8" : "border-line p-5"
      }`}
    >
      <div className="flex flex-wrap items-baseline justify-between gap-3">
        <div>
          <h3
            className={`font-medium text-paper-000 ${
              prominent && !asset ? "text-lg" : "text-[15px]"
            }`}
          >
            {slot.title}
            {!slot.required && (
              <span className="ml-2 text-xs font-normal text-paper-400">optional</span>
            )}
          </h3>
          <p className="mt-1 max-w-measure text-sm leading-relaxed text-paper-400">
            {slot.hint}
          </p>
        </div>

        {phase === "idle" && (
          <label
            className={`cursor-pointer rounded-[3px] text-sm transition ${
              prominent
                ? "bg-paper-000 px-5 py-2.5 font-medium text-ink-000 hover:bg-white"
                : "border border-line-strong px-4 py-2 text-paper-100 hover:bg-ink-200"
            }`}
          >
            {asset
              ? slot.role === "master"
                ? "Replace film"
                : slot.role === "subtitle"
                  ? "Replace subtitle file"
                  : "Replace poster"
              : prominent
                ? "Choose your film"
                : "Choose file"}
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

      {slot.role === "subtitle" && phase === "idle" && (
        <div className="mt-4">
          <label htmlFor="sub-lang" className="block text-sm text-paper-300">
            {asset ? "Subtitle language (if replacing)" : "What language are these subtitles in?"}
          </label>
          <input
            id="sub-lang"
            value={language}
            onChange={(event) => setLanguage(event.target.value)}
            placeholder="en"
            className="mt-2 w-28 rounded-[3px] border border-line bg-ink-000 px-3 py-1.5
                       font-mono text-sm text-paper-000 outline-none focus:border-line-strong"
          />
          <p className="mt-1.5 max-w-measure text-xs text-paper-400">
            Subtitle files do not record this, so Preflight cannot read it from
            the file. Some destinations require it.
          </p>
        </div>
      )}

      {phase === "sending" && (
        <div className="mt-4">
          <div className="h-[2px] w-full overflow-hidden rounded-full bg-ink-200">
            <div
              className="h-full bg-paper-200 transition-[width] duration-200"
              style={{ width: `${percent(progress)}%` }}
            />
          </div>
          {/* A percentage on its own tells somebody watching a long upload
              nothing about whether to keep waiting. */}
          <p className="mt-2 text-sm text-paper-300" role="status">
            {progress?.stalled
              ? "Still waiting on your connection"
              : "Uploading securely"}{" "}
            · {percent(progress)}%
            {progress && progress.total > 0 && (
              <span className="text-paper-400">
                {" "}
                · {formatBytes(progress.uploaded)} of {formatBytes(progress.total)}
              </span>
            )}
          </p>
          {progress?.stalled ? (
            <p className="mt-1 max-w-measure text-sm leading-relaxed text-paper-400">
              Nothing has moved for a little while. Preflight is still trying,
              and everything already sent is safe — if it gives up you will be
              able to carry on from here rather than start again.
            </p>
          ) : (
            remaining(progress) && (
              <p className="mt-1 text-sm text-paper-400">
                About {remaining(progress)} left at the current speed.
              </p>
            )
          )}
        </div>
      )}

      {phase === "measuring" && (
        <div className="mt-4">
          <Working label="Measuring your film" />
        </div>
      )}

      {failure && (
        <div
          role="alert"
          className="mt-4 border-l-2 border-stop bg-stop-bg/40 px-3 py-2.5"
        >
          <p className="text-sm text-paper-100">{failure}</p>
          {pending ? (
            <>
              <p className="mt-1 max-w-measure text-sm leading-relaxed text-paper-300">
                Everything already uploaded is still there. Continuing sends
                only what is missing, into the same file — you do not need to
                start a new delivery.
              </p>
              <button
                type="button"
                onClick={() => void send(pending.file, pending.url, pending.assetId)}
                className="mt-3 rounded-[3px] bg-paper-000 px-4 py-2 text-sm font-medium
                           text-ink-000 transition hover:bg-white"
              >
                Continue uploading
              </button>
            </>
          ) : (
            <p className="mt-1 text-sm text-paper-300">
              Choose the file again to retry.
            </p>
          )}
        </div>
      )}

      {asset && <Measured asset={asset} isMaster={slot.required} />}
    </section>
  );
}

/**
 * What the worker found, said briefly.
 *
 * The summary answers the only question someone has at this moment — did that
 * work, and is this the right file — in the words they would use about their
 * own film. Everything measured is still here, one disclosure away, with the
 * tool and version that produced it.
 */
function Measured({ asset, isMaster }: { asset: Asset; isMaster: boolean }) {
  const properties = (asset.measured_properties ?? {}) as Record<
    string,
    Record<string, unknown>
  >;
  const video = properties.video ?? {};
  const audio = properties.audio ?? {};

  const resolution = resolutionName(
    video.widthPx as number | undefined,
    video.heightPx as number | undefined,
  );
  const duration = formatDuration(video.durationSeconds as number | undefined);
  const frameRate = video.frameRate as number | undefined;
  const channels = audio.channels as number | undefined;

  const videoLine = [resolution, codecName(video.codec as string), frameRate ? `${frameRate} fps` : null]
    .filter(Boolean)
    .join(" · ");
  const channelLabel =
    channels === 1 ? "Mono" : channels === 2 ? "Stereo" : channels ? `${channels}-channel` : null;
  const audioLine = [
    channelLabel ? `${channelLabel} audio` : null,
    codecName(audio.codec as string),
  ]
    .filter(Boolean)
    .join(" · ");

  return (
    <div className="mt-5 border-t border-line pt-5">
      {isMaster && (
        <p className="text-[15px] text-paper-000">Your film was measured successfully</p>
      )}

      <div className="mt-2 space-y-0.5 text-sm text-paper-300">
        <p>
          <span className="text-paper-100">{asset.original_filename}</span>
          {duration && <span> · {duration}</span>}
          <span className="text-paper-400"> · {formatBytes(asset.byte_size)}</span>
        </p>
        {videoLine && <p>{videoLine}</p>}
        {audioLine && <p>{audioLine}</p>}
      </div>

      <details className="mt-5">
        <summary className="cursor-pointer text-xs text-paper-400 transition hover:text-paper-200">
          View technical measurements
        </summary>

        <div className="mt-3 border-l border-line pl-4">
          {Object.entries(properties)
            .filter(([, value]) => value && typeof value === "object")
            .map(([groupName, values]) => (
              <div key={groupName} className="mb-4">
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

          <h4 className="slate mb-2 text-paper-400">provenance</h4>
          <dl className="space-y-1.5">
            <Row label="sha256" value={asset.sha256} mono />
            <Row label="measured by" value={asset.inspector} />
            <Row label="tool version" value={asset.inspector_version} mono />
            <Row label="custody" value={asset.custody_state} />
            <Row label="original is immutable" value={asset.immutable} />
          </dl>
        </div>
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

function percent(progress: UploadProgress | null): number {
  if (!progress || progress.total === 0) return 0;
  return Math.min(100, Math.round((progress.uploaded / progress.total) * 100));
}

/** A time somebody can decide against, rather than a spinner. */
function remaining(progress: UploadProgress | null): string | null {
  if (!progress || !progress.bytesPerSecond || progress.bytesPerSecond <= 0) return null;
  const left = progress.total - progress.uploaded;
  if (left <= 0) return null;
  const seconds = left / progress.bytesPerSecond;
  if (seconds < 90) return "a minute";
  const minutes = Math.round(seconds / 60);
  if (minutes < 60) return `${minutes} minutes`;
  const hours = Math.floor(minutes / 60);
  return `${hours} hour${hours === 1 ? "" : "s"} ${minutes % 60} minutes`;
}
