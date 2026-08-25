"use client";

/**
 * Browser client for the Preflight API.
 *
 * Every call carries a Firebase ID token. The client never sends an owner id —
 * there is no parameter for one, because the server derives identity from the
 * token and would ignore it anyway.
 */

import { getIdToken } from "./auth";

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

export interface Project {
  id: string;
  title: string;
  project_type: string;
  primary_language: string | null;
  runtime_seconds: number | null;
  country_of_origin: string | null;
  state: string;
  created_at: string;
}

export interface Asset {
  id: string;
  role: string;
  original_filename: string;
  content_type: string;
  byte_size: number;
  sha256: string | null;
  custody_state: string;
  immutable: boolean;
  measured_properties: Record<string, unknown> | null;
  inspector: string | null;
  inspector_version: string | null;
}

export interface UploadIntent {
  asset_id: string;
  upload_url: string;
  expires_in_seconds: number;
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

  approvePlan: (projectId: string, planId: string, stepIds: string[]) =>
    call<{ plan_digest: string; approved_steps: number; note: string }>(
      `/v1/projects/${projectId}/repair-plans/${planId}/approve`,
      { method: "POST", body: JSON.stringify({ step_ids: stepIds }) },
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

export interface DestinationSource {
  url: string | null;
  retrieved_at: string;
  trust_tier: string;
  excerpt: string;
}

export interface Destination {
  id: string;
  slug: string;
  name: string;
  official_domain: string | null;
  requires_private_spec: boolean;
  available: boolean;
  rule_pack_id: string | null;
  rule_pack_version: number | null;
  rule_pack_digest: string | null;
  mandatory_rules: number;
  total_rules: number;
  sources: DestinationSource[];
  unavailable_reason: string | null;
}

export interface PlanStep {
  step_id: string;
  operation: string;
  safety: "green" | "yellow" | "red";
  destination_id: string;
  input_role: string;
  output_role: string;
  parameters: Record<string, unknown>;
  explains: string;
  executable: boolean;
  resolves: string[];
}

export interface RepairPlan {
  plan_id: string | null;
  digest: string;
  steps: PlanStep[];
  blocked: Record<string, unknown>[];
  unresolved: Record<string, unknown>[];
  preserved_assets: string[];
  estimated_seconds: number;
  shared_across_destinations: Record<string, string[]>;
}

export interface PreflightRun {
  run_id: string;
  comparison_digest: string;
  destinations: {
    destination_id: string;
    rule_pack_digest: string;
    satisfied: number;
    total: number;
    ready: boolean;
    blocking: string[];
    assertions: {
      rule_id: string;
      asset_type: string;
      field: string;
      published: string;
      measured: string | number | boolean | null;
      result: string;
      severity: string;
      source_url?: string | null;
      source_excerpt?: string | null;
      retrieved_at?: string | null;
      repair_operation?: string | null;
      explanation?: string;
    }[];
  }[];
  conflicts: Record<string, unknown>[];
  plan: RepairPlan;
  limitations: string[];
}

export interface JobStatus {
  job_id: string;
  type: string;
  state: string;
  attempt: number;
  error: string | null;
  message: string;
}

export interface PackageSummary {
  id: string;
  destination_id: string;
  destination_name: string;
  state: string;
  verified: boolean;
  package_sha256: string | null;
  rule_pack_version: number | null;
  rule_pack_digest: string | null;
  requirements_satisfied: string;
  files: { path: string; sha256: string }[];
  transformations: {
    operation: string;
    parameters: Record<string, unknown>;
    input_sha256: string | null;
    output_sha256: string | null;
    picture_preserved: boolean | null;
  }[];
  limitations: string[];
  validator_version: string | null;
  created_at: string;
}

export interface DeliveryRoom {
  room_id: string;
  url_token: string | null;
  recipient_label: string | null;
  expires_at: string;
  revoked_at: string | null;
  state: string;
  note: string;
}