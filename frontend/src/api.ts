import type {
  Artifact,
  Audit,
  AuditEvent,
  Mapping,
  Project,
  Readiness,
  RepairBundle,
  Scenario,
  Version,
} from "./types";

const API_ROOT =
  (import.meta.env.VITE_API_URL as string | undefined)?.replace(/\/$/, "") ??
  "";
const TOKEN_KEY = "polygraphml.session";

interface Envelope<T> {
  data: T | null;
  error: {
    code: string;
    message: string;
    detail?: Record<string, unknown>;
  } | null;
}

export class ApiError extends Error {
  constructor(
    message: string,
    readonly code: string,
    readonly status: number,
  ) {
    super(message);
  }
}

async function request<T>(
  path: string,
  init: RequestInit = {},
  authenticated = true,
): Promise<T> {
  const headers = new Headers(init.headers);
  if (init.body && !(init.body instanceof Blob))
    headers.set("Content-Type", "application/json");
  if (authenticated) {
    const token = await ensureSession();
    headers.set("Authorization", `Bearer ${token}`);
  }
  const response = await fetch(`${API_ROOT}${path}`, { ...init, headers });
  if (response.status === 204) return undefined as T;
  const payload = (await response.json()) as Envelope<T>;
  if (!response.ok || payload.error || payload.data === null) {
    throw new ApiError(
      payload.error?.message ??
        `Request failed with status ${response.status}.`,
      payload.error?.code ?? "REQUEST_FAILED",
      response.status,
    );
  }
  return payload.data;
}

export async function ensureSession(): Promise<string> {
  const existing = sessionStorage.getItem(TOKEN_KEY);
  if (existing) return existing;
  const session = await request<{ access_token: string }>(
    "/api/v1/sessions",
    { method: "POST" },
    false,
  );
  sessionStorage.setItem(TOKEN_KEY, session.access_token);
  return session.access_token;
}

export const api = {
  readiness: async (): Promise<Readiness> => {
    const response = await fetch(`${API_ROOT}/readyz`);
    if (!response.ok)
      throw new ApiError("API is not ready.", "NOT_READY", response.status);
    return (await response.json()) as Readiness;
  },
  version: async (): Promise<Version> => {
    const response = await fetch(`${API_ROOT}/version`);
    if (!response.ok)
      throw new ApiError(
        "Version metadata is unavailable.",
        "NOT_READY",
        response.status,
      );
    return (await response.json()) as Version;
  },
  benchmarkProject: (benchmarkId = "synthetic_campaign_leak_v1") =>
    request<Project>("/api/v1/projects/from-benchmark", {
      method: "POST",
      body: JSON.stringify({ benchmark_id: benchmarkId }),
    }),
  githubProject: (repositoryUrl: string, ref: string) =>
    request<Project>("/api/v1/projects", {
      method: "POST",
      body: JSON.stringify({
        name: repositoryUrl.split("/").at(-1) ?? "GitHub audit",
        source: { type: "github", repository_url: repositoryUrl, ref },
      }),
    }),
  uploadProject: (name: string) =>
    request<Project>("/api/v1/projects", {
      method: "POST",
      body: JSON.stringify({ name, source: { type: "upload" } }),
    }),
  project: (projectId: string) =>
    request<Project>(`/api/v1/projects/${projectId}`),
  mapProject: (projectId: string, mapping: Mapping) =>
    request<Project>(`/api/v1/projects/${projectId}/mapping`, {
      method: "PATCH",
      body: JSON.stringify(mapping),
    }),
  scenario: (projectId: string, scenario: Scenario) =>
    request<Project>(`/api/v1/projects/${projectId}/scenario`, {
      method: "PUT",
      body: JSON.stringify(scenario),
    }),
  startAudit: (projectId: string, scenarioRevision: number) =>
    request<Audit>("/api/v1/audits", {
      method: "POST",
      headers: { "Idempotency-Key": crypto.randomUUID() },
      body: JSON.stringify({
        project_id: projectId,
        scenario_revision: scenarioRevision,
        mode: "complete_audit",
      }),
    }),
  audit: (auditId: string) => request<Audit>(`/api/v1/audits/${auditId}`),
  events: (auditId: string, afterSequence: number) =>
    request<AuditEvent[]>(
      `/api/v1/audits/${auditId}/events?after_sequence=${afterSequence}`,
      {
        headers: { Accept: "application/json" },
      },
    ),
  streamEvents: async (
    auditId: string,
    afterSequence: number,
    lastEventId: string | null,
    onEvent: (event: AuditEvent) => void,
    signal: AbortSignal,
  ): Promise<void> => {
    const token = await ensureSession();
    const headers = new Headers({
      Accept: "text/event-stream",
      Authorization: `Bearer ${token}`,
    });
    if (lastEventId) headers.set("Last-Event-ID", lastEventId);
    const response = await fetch(
      `${API_ROOT}/api/v1/audits/${auditId}/events?after_sequence=${afterSequence}`,
      { headers, signal },
    );
    if (!response.ok || !response.body)
      throw new ApiError(
        "Decision Trace stream is unavailable.",
        "EVENT_STREAM_FAILED",
        response.status,
      );
    const reader = response.body.getReader();
    const decoder = new TextDecoder();
    let buffer = "";
    while (true) {
      const { done, value } = await reader.read();
      buffer += decoder
        .decode(value, { stream: !done })
        .replaceAll("\r\n", "\n");
      let boundary = buffer.indexOf("\n\n");
      while (boundary >= 0) {
        const frame = buffer.slice(0, boundary);
        buffer = buffer.slice(boundary + 2);
        const data = frame
          .split("\n")
          .filter((line) => line.startsWith("data:"))
          .map((line) => line.slice(5).trimStart())
          .join("\n");
        if (data) onEvent(JSON.parse(data) as AuditEvent);
        boundary = buffer.indexOf("\n\n");
      }
      if (done) return;
    }
  },
  answer: (auditId: string, questionId: string, answer: string) =>
    request<Audit>(`/api/v1/audits/${auditId}/answers`, {
      method: "POST",
      headers: { "Idempotency-Key": crypto.randomUUID() },
      body: JSON.stringify({ question_id: questionId, answer }),
    }),
  report: (auditId: string, audience: "technical" | "executive") =>
    request<{ report_id: string; content: string }>(
      `/api/v1/audits/${auditId}/report`,
      {
        method: "POST",
        body: JSON.stringify({ audience, format: "markdown" }),
      },
    ),
  repairBundle: (auditId: string) =>
    request<RepairBundle>(`/api/v1/audits/${auditId}/repair-bundle`, {
      method: "POST",
    }),
  downloadRepair: async (url: string): Promise<Blob> => {
    const isLocalApiDownload = url.startsWith("/");
    const headers = new Headers();
    if (isLocalApiDownload) {
      const token = await ensureSession();
      headers.set("Authorization", `Bearer ${token}`);
    }
    const response = await fetch(
      isLocalApiDownload ? `${API_ROOT}${url}` : url,
      {
        headers,
      },
    );
    if (!response.ok)
      throw new ApiError(
        "Repair bundle download failed.",
        "REPAIR_DOWNLOAD_FAILED",
        response.status,
      );
    return response.blob();
  },
  declareUploads: (projectId: string, artifacts: Record<string, unknown>[]) =>
    request<{
      uploads: Array<{
        artifact_id: string;
        client_id: string;
        url: string;
        headers: Record<string, string>;
      }>;
    }>(`/api/v1/projects/${projectId}/artifacts/presign`, {
      method: "POST",
      body: JSON.stringify({ artifacts }),
    }),
  putUpload: async (
    url: string,
    file: File,
    requiredHeaders: Record<string, string>,
  ): Promise<void> => {
    const isLocalApiUpload = url.startsWith("/");
    const headers = new Headers(requiredHeaders);
    if (isLocalApiUpload) {
      const token = await ensureSession();
      headers.set("Authorization", `Bearer ${token}`);
    }
    const response = await fetch(isLocalApiUpload ? `${API_ROOT}${url}` : url, {
      method: "PUT",
      headers,
      body: file,
    });
    if (!response.ok)
      throw new ApiError(
        "Artifact upload failed.",
        "UPLOAD_FAILED",
        response.status,
      );
  },
  completeUploads: (projectId: string, artifactIds: string[]) =>
    request<Project>(`/api/v1/projects/${projectId}/artifacts/complete`, {
      method: "POST",
      body: JSON.stringify({ artifact_ids: artifactIds }),
    }),
};

export function artifactKind(file: File): Artifact["kind"] | null {
  const suffix = file.name.split(".").at(-1)?.toLowerCase();
  if (suffix === "csv" || suffix === "parquet") return "dataset";
  if (["skops", "json", "ubj", "onnx"].includes(suffix ?? "")) return "model";
  if (suffix === "ipynb") return "notebook";
  if (suffix === "yaml" || suffix === "yml") return "manifest";
  if (["py", "txt", "md"].includes(suffix ?? "")) return "source";
  return null;
}

export async function sha256(file: File): Promise<string> {
  const bytes = await file.arrayBuffer();
  const digest = await crypto.subtle.digest("SHA-256", bytes);
  return [...new Uint8Array(digest)]
    .map((value) => value.toString(16).padStart(2, "0"))
    .join("");
}
