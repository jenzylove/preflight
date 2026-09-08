"use client";

/**
 * Browser client for the Preflight API.
 *
 * Every call carries a Firebase ID token. The client never sends an owner id —
 * there is no parameter for one, because the server derives identity from the
 * token and would ignore it anyway.
 */

import { getIdToken } from "./auth";
import type {
  DestinationResearch,
  Asset,
  Destination,
  DeliveryRoom,
  JobStatus,
  PackageSummary,
  Passport,
  Plan,
  PreflightRun,
  Project,
  Rule,
  UploadIntent,
} from "./types";

// Re-exported so call sites can import the client and the shapes it returns
// from one place. The definitions live in ./types, which mirrors the API.
export type {
  Assertion,
  Asset,
  Conflict,
  DeliveryRoom,
  Destination,
  DestinationMatrix,
  JobStatus,
  PackageFile,
  PackageSummary,
  Passport,
  Plan,
  PlanStep,
  PreflightRun,
  Project,
  PublicRoom,
  Rule,
  Source,
  Transformation,
  UploadIntent,
} from "./types";

export const API_BASE =
  process.env.NEXT_PUBLIC_API_BASE_URL ??
  "https://preflight-api-584136898465.us-central1.run.app";

export class ApiError extends Error {
  constructor(
    readonly status: number,
    message: string,
  ) {
    super(message);
  }
}

async function call<T>(path: string, init: RequestInit = {}): Promise<T> {
  const token = await getIdToken();
  const res = await fetch(`${API_BASE}${path}`, {
    ...init,
    headers: {
      "Content-Type": "application/json",
      ...(token ? { Authorization: `Bearer ${token}` } : {}),
      ...(init.headers ?? {}),
    },
  });

  if (!res.ok) {
    // The API returns copy written for a producer, not a stack trace. Surface
    // it as-is rather than replacing it with something vaguer.
    let detail = `Request failed (${res.status})`;
    try {
      const body = await res.json();
      if (typeof body?.detail === "string") detail = body.detail;
    } catch {
      /* response had no JSON body */
    }
    throw new ApiError(res.status, detail);
  }

  if (res.status === 204) return undefined as T;
  return res.json();
}

export const api = {
  listProjects: () => call<Project[]>("/v1/projects"),

  getProject: (id: string) => call<Project>(`/v1/projects/${id}`),

  createProject: (body: {
    title: string;
    project_type: string;
    primary_language?: string;
    runtime_seconds?: number;
    country_of_origin?: string;
    synopsis?: string;
  }) =>
    call<Project>("/v1/projects", {
      method: "POST",
      body: JSON.stringify(body),
    }),

  listAssets: (projectId: string) =>
    call<Asset[]>(`/v1/projects/${projectId}/assets`),

  uploadIntent: (
    projectId: string,
    body: {
      role: string;
      filename: string;
      content_type: string;
      byte_size: number;
      /** Only ever what the user told us; never inferred from the film. */
      language?: string;
    },
  ) =>
    call<UploadIntent>(`/v1/projects/${projectId}/assets/upload-intent`, {
      method: "POST",
      body: JSON.stringify(body),
    }),

  completeUpload: (projectId: string, assetId: string) =>
    call<Asset>(`/v1/projects/${projectId}/assets/${assetId}/complete`, {
      method: "POST",
    }),

  listDestinations: () => call<Destination[]>("/v1/destinations"),

  /**
   * Ask what a destination currently publishes.
   *
   * Returns straight away with something to watch. The search, the reading and
   * the extraction happen on the server and take minutes, so the browser polls
   * rather than waiting on one long request that a flaky connection would drop.
   */
  researchDestination: (query: string) =>
    call<DestinationResearch>("/v1/destinations/research", {
      method: "POST",
      body: JSON.stringify({ query }),
    }),

  readResearch: (jobId: string) =>
    call<DestinationResearch>(`/v1/destinations/research/${jobId}`),

  /** Every requirement this project will be measured against, with evidence. */
  listRules: (projectId: string) =>
    call<Rule[]>(`/v1/projects/${projectId}/rules`),

  /**
   * Record the owner's judgement about one extracted requirement.
   *
   * Setting a rule aside is not a delete. The rule stays in the pack, the
   * decision is attributed, and it surfaces on the passport as a stated
   * limitation — which is why a reason is required rather than optional.
   */
  setDisposition: (
    projectId: string,
    ruleId: string,
    action: "accept" | "set_aside",
    reason: string,
  ) =>
    call<{ rule_id: string; action: string; reason: string; note: string }>(
      `/v1/projects/${projectId}/rules/${ruleId}/disposition`,
      { method: "PUT", body: JSON.stringify({ action, reason }) },
    ),

  getSelectedDestinations: (projectId: string) =>
    call<{ selected: Destination[]; project_state: string }>(
      `/v1/projects/${projectId}/destinations`,
    ),

  setDestinations: (projectId: string, destinationIds: string[]) =>
    call<{ selected: Destination[]; project_state: string }>(
      `/v1/projects/${projectId}/destinations`,
      { method: "PUT", body: JSON.stringify({ destination_ids: destinationIds }) },
    ),

  runPreflight: (projectId: string) =>
    call<PreflightRun>(`/v1/projects/${projectId}/preflight`, { method: "POST" }),

  latestPreflight: (projectId: string) =>
    call<PreflightRun>(`/v1/projects/${projectId}/preflight/latest`),

  // The digest is what the user is consenting to, so it travels with the
  // approval. If the plan has changed since it was displayed, the server
  // refuses rather than approving work nobody saw.
  approvePlan: (
    projectId: string,
    planId: string,
    planDigest: string,
    stepIds: string[],
  ) =>
    call<{ plan_digest: string; approved_steps: string[]; note: string }>(
      `/v1/projects/${projectId}/repair-plans/${planId}/approve`,
      {
        method: "POST",
        body: JSON.stringify({
          plan_digest: planDigest,
          approved_step_ids: stepIds,
        }),
      },
    ),

  executePlan: (projectId: string, planId: string) =>
    call<{ job_id: string; state: string; steps_queued: number; message: string }>(
      `/v1/projects/${projectId}/repair-plans/${planId}/execute`,
      { method: "POST" },
    ),

  jobStatus: (projectId: string, jobId: string) =>
    call<JobStatus>(`/v1/projects/${projectId}/jobs/${jobId}`),

  listPackages: (projectId: string) =>
    call<PackageSummary[]>(`/v1/projects/${projectId}/packages`),

  packageDownload: (projectId: string, packageId: string) =>
    call<{ url: string; expires_in_seconds: number; sha256: string | null }>(
      `/v1/projects/${projectId}/packages/${packageId}/download-intent`,
      { method: "POST" },
    ),

  getPassport: (projectId: string) =>
    call<{
      version: number;
      digest: string;
      issued_at: string;
      passport: Record<string, unknown>;
      report: string;
    }>(`/v1/projects/${projectId}/passport`),

  listRooms: (projectId: string) =>
    call<DeliveryRoom[]>(`/v1/projects/${projectId}/delivery-rooms`),

  createRoom: (
    projectId: string,
    packageId: string,
    body: { recipient_label?: string; expires_in_hours?: number },
  ) =>
    call<DeliveryRoom>(
      `/v1/projects/${projectId}/packages/${packageId}/delivery-rooms`,
      { method: "POST", body: JSON.stringify(body) },
    ),

  revokeRoom: (projectId: string, roomId: string) =>
    call<{ state: string; note: string }>(
      `/v1/projects/${projectId}/delivery-rooms/${roomId}`,
      { method: "DELETE" },
    ),
};

/**
 * Send bytes straight to Cloud Storage using the resumable session the API
 * issued. The file never passes through the Preflight API, which is why a
 * feature-length master is possible at all.
 */
/** How the upload is going, in terms the interface can speak plainly about. */
export interface UploadProgress {
  /** Bytes the server has acknowledged, not bytes handed to the socket. */
  uploaded: number;
  total: number;
  /** Bytes per second over the recent past, once there is enough to judge. */
  bytesPerSecond: number | null;
  /** True when nothing has been acknowledged for a while. */
  stalled: boolean;
}

export class UploadInterrupted extends Error {
  /** Bytes safely committed, so the same upload can be continued. */
  readonly uploaded: number;

  constructor(message: string, uploaded: number) {
    super(message);
    this.name = "UploadInterrupted";
    this.uploaded = uploaded;
  }
}

//: Cloud Storage requires resumable chunks to be a multiple of 256 KiB.
const CHUNK = 8 * 1024 * 1024;
const CHUNK_TIMEOUT_MS = 120_000;
const STALL_AFTER_MS = 45_000;

/**
 * Send a file to its resumable session, one chunk at a time.
 *
 * This was a single PUT of the whole file. Three things followed from that,
 * and a 275 MB upload found all of them: progress came from
 * `xhr.upload.onprogress`, which counts bytes handed to the socket rather than
 * bytes the server has accepted, so the bar ran ahead of the wire and then sat
 * still; there was no timeout, so a dead connection was indistinguishable from
 * a slow one and waited forever; and there was no way back afterwards except
 * starting the whole project again.
 *
 * Chunking fixes all three at once. Every chunk is acknowledged, so progress is
 * a fact rather than an estimate; a chunk that does not complete in time fails
 * rather than hanging; and the session can be asked what it already holds, so
 * continuing costs only what was not yet sent. The object is the same object
 * either way, so resuming cannot duplicate or corrupt the asset.
 */
export async function uploadToSignedUrl(
  url: string,
  file: File,
  onProgress?: (progress: UploadProgress) => void,
  signal?: AbortSignal,
): Promise<void> {
  const total = file.size;
  let uploaded = await committedBytes(url, total);

  // Recent throughput, so "slow" and "stopped" can be told apart.
  let lastMovedAt = Date.now();
  let lastMovedBytes = uploaded;

  const report = (stalled = false) => {
    const seconds = (Date.now() - lastMovedAt) / 1000;
    const moved = uploaded - lastMovedBytes;
    onProgress?.({
      uploaded,
      total,
      bytesPerSecond: seconds > 1 && moved > 0 ? moved / seconds : null,
      stalled,
    });
  };
  report();

  while (uploaded < total) {
    if (signal?.aborted) throw new UploadInterrupted("Upload paused.", uploaded);

    const end = Math.min(uploaded + CHUNK, total);
    const watchdog = setInterval(() => report(Date.now() - lastMovedAt > STALL_AFTER_MS), 5000);

    try {
      const status = await putChunk(url, file.slice(uploaded, end), uploaded, end - 1, total, signal);
      if (status === 308 || status === 200 || status === 201) {
        const rate = (end - uploaded) / Math.max(1, (Date.now() - lastMovedAt) / 1000);
        lastMovedBytes = uploaded;
        lastMovedAt = Date.now();
        uploaded = end;
        onProgress?.({ uploaded, total, bytesPerSecond: rate, stalled: false });
      } else {
        throw new UploadInterrupted(`The upload was refused (${status}).`, uploaded);
      }
    } catch (caught) {
      if (caught instanceof UploadInterrupted) throw caught;
      // Ask the session what it actually holds before reporting a position:
      // a chunk can be committed even when the response never arrives.
      const confirmed = await committedBytes(url, total).catch(() => uploaded);
      throw new UploadInterrupted(
        "The connection dropped before your film finished uploading.",
        confirmed,
      );
    } finally {
      clearInterval(watchdog);
    }
  }
}

/** How much of this upload the server already has. */
async function committedBytes(url: string, total: number): Promise<number> {
  return new Promise((resolve) => {
    const xhr = new XMLHttpRequest();
    xhr.open("PUT", url, true);
    xhr.setRequestHeader("Content-Range", `bytes */${total}`);
    xhr.timeout = 30_000;
    xhr.onload = () => {
      if (xhr.status === 200 || xhr.status === 201) return resolve(total);
      const range = xhr.getResponseHeader("Range");
      const match = range?.match(/bytes=0-(\d+)/);
      resolve(match ? Number(match[1]) + 1 : 0);
    };
    // A session that cannot be queried is treated as empty, which is safe:
    // re-sending a chunk overwrites the same bytes of the same object.
    xhr.onerror = () => resolve(0);
    xhr.ontimeout = () => resolve(0);
    xhr.send();
  });
}

function putChunk(
  url: string,
  blob: Blob,
  start: number,
  end: number,
  total: number,
  signal?: AbortSignal,
): Promise<number> {
  return new Promise((resolve, reject) => {
    const xhr = new XMLHttpRequest();
    xhr.open("PUT", url, true);
    xhr.setRequestHeader("Content-Range", `bytes ${start}-${end}/${total}`);
    xhr.timeout = CHUNK_TIMEOUT_MS;
    xhr.onload = () => resolve(xhr.status);
    xhr.onerror = () => reject(new Error("network"));
    xhr.ontimeout = () => reject(new Error("timeout"));
    signal?.addEventListener("abort", () => xhr.abort(), { once: true });
    xhr.send(blob);
  });
}


// ---------------------------------------------------------------------------
// Destinations, preflight, plan, packages, passport, delivery
// ---------------------------------------------------------------------------
