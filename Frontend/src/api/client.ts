import type {
  AssessmentInput,
  Frameworks,
  Note,
  PipelineStage,
  Scores,
  ScorePreviewInput,
  StartupDetail,
  StartupInput,
  StartupSummary,
} from "./types";

const BASE = import.meta.env.VITE_API_BASE ?? "/api";

async function request<T>(path: string, init?: RequestInit): Promise<T> {
  const res = await fetch(`${BASE}${path}`, {
    ...init,
    headers: { "Content-Type": "application/json", ...init?.headers },
  });
  if (!res.ok) {
    const body = await res.json().catch(() => null);
    throw new Error(errorMessage(body?.detail) ?? `${res.status} ${res.statusText}`);
  }
  return res.json() as Promise<T>;
}

/** FastAPI returns either a string or a list of validation errors. */
function errorMessage(detail: unknown): string | null {
  if (typeof detail === "string") return detail;
  if (Array.isArray(detail)) return detail.map((d) => d?.msg ?? String(d)).join("; ");
  return null;
}

const post = <T>(path: string, body: unknown) => request<T>(path, { method: "POST", body: JSON.stringify(body) });
const slugPath = (slug: string) => `/startups/${encodeURIComponent(slug)}`;

export const api = {
  startups: () => request<StartupSummary[]>("/startups"),
  startup: (slug: string) => request<StartupDetail>(slugPath(slug)),
  createStartup: (input: StartupInput) => post<StartupDetail>("/startups", input),
  addAssessment: (slug: string, input: AssessmentInput) => post<StartupDetail>(`${slugPath(slug)}/assessments`, input),
  previewScores: (input: ScorePreviewInput) => post<Scores>("/scoring/preview", input),
  compare: (slugs: string[]) => request<StartupDetail[]>(`/compare?${new URLSearchParams({ slugs: slugs.join(",") })}`),
  frameworks: () => request<Frameworks>("/frameworks"),
  setPipeline: (slug: string, pipeline_stage: PipelineStage) =>
    request<StartupSummary>(`${slugPath(slug)}/pipeline`, {
      method: "PATCH",
      body: JSON.stringify({ pipeline_stage }),
    }),
  addNote: (slug: string, body: string) => post<Note>(`${slugPath(slug)}/notes`, { body }),
};
