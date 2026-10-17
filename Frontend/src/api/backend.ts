import type {
  Frameworks,
  FundingEvent,
  InvestmentMemo,
  NaturalLanguageSearchResponse,
  Peer,
  ResearchJob,
  ScrapeAgentInfo,
  ScrapedStartupAdded,
  ScrapeJob,
  ScrapeRecord,
  ScrapeRequest,
  StartupDetail,
  StartupSummary,
} from "./backend-types";

// Client for the FastAPI backend. In development Vite proxies /api to it (vite.config.ts).
const BASE = "/api";

/** A failed request, carrying the HTTP status (e.g. 404 for a startup that isn't in the database). */
export class ApiError extends Error {
  constructor(
    message: string,
    readonly status: number,
  ) {
    super(message);
  }
}

async function request<T>(path: string, init?: RequestInit): Promise<T> {
  let res: Response;
  try {
    res = await fetch(`${BASE}${path}`, {
      ...init,
      headers: { "Content-Type": "application/json", ...init?.headers },
    });
  } catch {
    throw new ApiError("Couldn't reach the backend. Is it running on port 8000?", 0);
  }
  if (!res.ok) {
    const body = (await res.json().catch(() => null)) as { detail?: unknown } | null;
    throw new ApiError(errorMessage(body?.detail) ?? `${res.status} ${res.statusText}`, res.status);
  }
  return (await res.json()) as T;
}

/** FastAPI returns `detail` as a string, or as a list of validation errors. */
function errorMessage(detail: unknown): string | null {
  if (typeof detail === "string") return detail;
  if (Array.isArray(detail))
    return detail.map((d: { msg?: string }) => d?.msg ?? String(d)).join("; ");
  return null;
}

const startupPath = (slug: string) => `/startups/${encodeURIComponent(slug)}`;

export const backend = {
  /** sort: potential (default), readiness, ocean, momentum, investment, trl, brl or name; ranked by the backend. */
  startups: (sort?: string) =>
    request<StartupSummary[]>(sort ? `/startups?sort=${encodeURIComponent(sort)}` : "/startups"),
  startup: (slug: string) => request<StartupDetail>(startupPath(slug)),
  memo: (slug: string) => request<InvestmentMemo>(`${startupPath(slug)}/memo`),
  /** Natural-language search (LightRAG). 503 when search isn't configured, 502 when it failed. */
  search: (query: string) =>
    request<NaturalLanguageSearchResponse>("/startups/search", {
      method: "POST",
      body: JSON.stringify({ query }),
    }),
  /** Queue the research agent on a startup that has no score yet. 409 when it was researched recently or already scored. */
  startResearch: (slug: string) =>
    request<ResearchJob>("/research", { method: "POST", body: JSON.stringify({ slug }) }),
  researchJob: (id: number) => request<ResearchJob>(`/research/${id}`),
  /** The scrape agent's model, and whether it reads PDFs and images and searches the web. */
  scrapeInfo: () => request<ScrapeAgentInfo>("/agent-scrape/info"),
  /** Queue the scrape agent on up to 8 sources, read in turn and merged into one result. Poll scrapeJob. */
  startScrape: (body: ScrapeRequest) =>
    request<ScrapeJob>("/agent-scrape", { method: "POST", body: JSON.stringify(body) }),
  scrapeJob: (id: number) => request<ScrapeJob>(`/agent-scrape/${id}`),
  /** Add a scraped startup to the database (a sourced startup without a score). 422 without a website. */
  addScrapedStartup: (record: ScrapeRecord, website?: string) =>
    request<ScrapedStartupAdded>("/agent-scrape/startups", {
      method: "POST",
      body: JSON.stringify(website ? { record, website } : { record }),
    }),
  frameworks: () => request<Frameworks>("/frameworks"),
  /** Every funding event from every source, oldest first. */
  rounds: (slug: string) => request<FundingEvent[]>(`${startupPath(slug)}/rounds`),
  peers: (slug: string) => request<Peer[]>(`${startupPath(slug)}/peers`),
};
