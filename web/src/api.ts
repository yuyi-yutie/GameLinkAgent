import type {
  AppConfig,
  ArtifactText,
  DirListing,
  Health,
  Job,
  OptionsResponse,
  ProjectInfo,
} from "./types";

export class ApiError extends Error {}

async function request<T>(path: string, init?: RequestInit): Promise<T> {
  const headers = new Headers(init?.headers);
  if (init?.body) headers.set("Content-Type", "application/json");

  const response = await fetch(path, { ...init, headers });
  if (!response.ok) {
    let message = `${response.status} ${response.statusText}`;
    try {
      const body = (await response.json()) as { detail?: unknown; error?: unknown };
      const detail = body.detail ?? body.error;
      if (detail) {
        message = typeof detail === "string" ? detail : JSON.stringify(detail);
      }
    } catch {
      // keep the status line
    }
    throw new ApiError(message);
  }
  return (await response.json()) as T;
}

export const api = {
  health: () => request<Health>("/api/health"),
  options: () => request<OptionsResponse>("/api/options"),
  schema: (name: "protocol" | "architecture") =>
    request<Record<string, unknown>>(`/api/schemas/${name}`),
  config: () => request<AppConfig>("/api/config"),
  saveConfig: (payload: {
    base_url?: string;
    model?: string;
    api_key?: string;
    godot_bin?: string;
  }) => request<AppConfig>("/api/config", { method: "PUT", body: JSON.stringify(payload) }),

  dirs: (path?: string) =>
    request<DirListing>(`/api/fs/dirs${path ? `?path=${encodeURIComponent(path)}` : ""}`),
  project: (path: string) => request<ProjectInfo>(`/api/projects?path=${encodeURIComponent(path)}`),

  artifact: (path: string) =>
    request<ArtifactText>(`/api/artifacts?path=${encodeURIComponent(path)}`),
  saveArtifact: (path: string, text: string) =>
    request<{ path: string; bytes: number }>("/api/artifacts", {
      method: "PUT",
      body: JSON.stringify({ path, text }),
    }),

  jobs: () => request<Job[]>("/api/jobs"),
  job: (id: string) => request<Job>(`/api/jobs/${id}`),
  submitJob: (kind: string, params: Record<string, unknown>) =>
    request<Job>("/api/jobs", { method: "POST", body: JSON.stringify({ kind, params }) }),
  cancelJob: (id: string) =>
    request<{ cancelled: boolean }>(`/api/jobs/${id}/cancel`, { method: "POST" }),
};
