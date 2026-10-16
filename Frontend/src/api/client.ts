import type {
  FilterOptions,
  Frameworks,
  Note,
  PipelineStage,
  StartupDetail,
  StartupQuery,
  StartupSummary,
} from "./types";

const BASE = import.meta.env.VITE_API_BASE ?? "/api";

async function request<T>(path: string, init?: RequestInit): Promise<T> {
  const res = await fetch(`${BASE}${path}`, {
    ...init,
    headers: { "Content-Type": "application/json", ...init?.headers },
  });
  if (!res.ok) {
    const detail = await res.json().catch(() => null);
    throw new Error(detail?.detail ?? `${res.status} ${res.statusText}`);
  }
  return res.json() as Promise<T>;
}

function qs(params: Record<string, string | undefined>): string {
  const entries = Object.entries(params).filter(([, v]) => v !== undefined && v !== "");
  return entries.length ? `?${new URLSearchParams(entries as [string, string][])}` : "";
}

export const api = {
  startups: (query: StartupQuery = {}) => request<StartupSummary[]>(`/startups${qs({ ...query })}`),
  startup: (slug: string) => request<StartupDetail>(`/startups/${encodeURIComponent(slug)}`),
  compare: (slugs: string[]) => request<StartupDetail[]>(`/compare${qs({ slugs: slugs.join(",") })}`),
  filters: () => request<FilterOptions>("/filters"),
  frameworks: () => request<Frameworks>("/frameworks"),
  setPipeline: (slug: string, pipeline_stage: PipelineStage) =>
    request<StartupSummary>(`/startups/${encodeURIComponent(slug)}/pipeline`, {
      method: "PATCH",
      body: JSON.stringify({ pipeline_stage }),
    }),
  addNote: (slug: string, body: string) =>
    request<Note>(`/startups/${encodeURIComponent(slug)}/notes`, {
      method: "POST",
      body: JSON.stringify({ body }),
    }),
};
