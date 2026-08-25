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
