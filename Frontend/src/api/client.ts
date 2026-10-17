import { seed, frameworks } from "./mock-data";
import type { NaturalLanguageSearchResponse, PipelineStage, StartupDetail } from "./types";
import { previewScores, type AssessmentDraft, type CompanyDraft } from "../lib/assessment";
// Mock transport retains the original API method boundaries. Replace these handlers with your real client.
let startups: StartupDetail[] = structuredClone(seed);
export const api = {
  async listStartups() {
    return structuredClone(startups);
  },
  // Matches the supplied POST /api/startups/search response contract; preview-only transport.
  async searchStartups(query: string): Promise<NaturalLanguageSearchResponse> {
    const stopWords = new Set("and are for from that the with startups startup companies company show find".split(" "));
    const terms = [...new Set(query.toLowerCase().split(/[^\p{L}\p{N}]+/u).filter((term) => term.length > 2 && !stopWords.has(term)))];
    const scored = startups.map((startup) => {
      const text = `${startup.name} ${startup.tagline} ${startup.description} ${startup.sector} ${startup.country} ${startup.region}`.toLowerCase();
      return { startup, matched: terms.filter((term) => text.includes(term)) };
    }).filter((match) => match.matched.length > 0).sort((a, b) => b.matched.length - a.matched.length);
    const top = scored[0]?.matched.length ?? 1;
    return {
      query,
      results: scored.map(({ startup, matched }) => ({ ...structuredClone(startup), relevance: matched.length / top, matched, entry: null })),
      entries: [],
    };
  },
  async frameworks() {
    return frameworks;
  },
  async startup(slug: string) {
    const s = startups.find((s) => s.slug === slug);
    if (!s) throw new Error("Startup not found");
    return structuredClone(s);
  },
  async compare(slugs: string[]) {
    return Promise.all([...new Set(slugs)].slice(0, 3).map((slug) => api.startup(slug)));
  },
  async setPipeline(slug: string, stage: PipelineStage) {
    const s = await api.startup(slug);
    s.pipeline_stage = stage;
    startups = startups.map((o) => (o.slug === slug ? s : o));
    return s;
  },
  async addNote(slug: string, body: string) {
    const s = await api.startup(slug);
    const n = {
      id: crypto.randomUUID(),
      body,
      author: "Preview analyst",
      created_at: new Date().toISOString().replace("Z", ""),
    };
    s.notes.unshift(n);
    startups = startups.map((o) => (o.slug === slug ? s : o));
    return n;
  },
  async createStartup({ company, draft }: { company: CompanyDraft; draft: AssessmentDraft }) {
    const slug =
      company.name
        .toLowerCase()
        .replace(/[^a-z0-9]+/g, "-")
        .replace(/^-|-$/g, "") +
      "-" +
      crypto.randomUUID().slice(0, 6);
    const base = seed[0];
    if (!base) throw new Error("Missing preview seed");
    const s: StartupDetail = {
      ...structuredClone(base),
      ...company,
      slug,
      region: "",
      city: "",
      founded_year: null,
      last_round_on: company.roundDate || null,
      pipeline_stage: "sourced",
      total_disclosed_usd: 0,
      funding_rounds: [],
      notes: [],
      sources: [],
    };
    startups.push(s);
    return api.addAssessment(slug, draft);
  },
  async addAssessment(slug: string, draft: AssessmentDraft) {
    const s = await api.startup(slug);
    s.levels = { ...draft.levels };
    s.readiness = {
      ...draft.levels,
      assessor: draft.assessor,
      confidence: draft.confidence,
      rationale: draft.rationale,
      assessed_on: new Date().toISOString().slice(0, 10),
    };
    s.ocean_kpis = Object.values(draft.kpis);
    s.scores = previewScores(draft);
    startups = startups.map((o) => (o.slug === slug ? s : o));
    return s;
  },
  async scorePreview(input: { draft: AssessmentDraft }) {
    return previewScores(input.draft);
  },
  // Landing dashboards. Mock of the backend endpoint — swap for the real fetch
  // once the backend exposes newest / trending / top ocean-impact data.
  async landingDashboard() {
    const byNewest = [...startups].sort((a, b) =>
      (b.created_at ?? "").localeCompare(a.created_at ?? ""),
    );
    const byGrowth = [...startups].sort((a, b) => (b.growth_speed ?? 0) - (a.growth_speed ?? 0));
    const byImpact = [...startups].sort((a, b) => b.scores.ocean_impact - a.scores.ocean_impact);
    return structuredClone({
      newest: byNewest.slice(0, 5),
      trending: byGrowth.slice(0, 5),
      topImpact: byImpact.slice(0, 3),
    });
  },
};
