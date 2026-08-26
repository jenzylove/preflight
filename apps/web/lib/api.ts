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
export async function uploadToSignedUrl(
  url: string,
  file: File,
  onProgress?: (fraction: number) => void,
): Promise<void> {
  return new Promise((resolve, reject) => {
    const xhr = new XMLHttpRequest();
    xhr.open("PUT", url, true);
    xhr.setRequestHeader("Content-Type", file.type);

    xhr.upload.onprogress = (e) => {
      if (e.lengthComputable && onProgress) onProgress(e.loaded / e.total);
    };
    xhr.onload = () =>
      xhr.status >= 200 && xhr.status < 300
        ? resolve()
        : reject(new Error(`Upload failed (${xhr.status})`));
    xhr.onerror = () => reject(new Error("Upload failed. Check your connection."));

    xhr.send(file);
  });
}

// ---------------------------------------------------------------------------
// Destinations, preflight, plan, packages, passport, delivery
// ---------------------------------------------------------------------------
