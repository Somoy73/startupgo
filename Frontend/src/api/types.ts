export const PIPELINE_STAGES = ["sourced", "screening", "diligence", "term-sheet", "invested", "passed"] as const;
export type PipelineStage = (typeof PIPELINE_STAGES)[number];
export type Confidence = "low" | "medium" | "high";
export const DIMENSIONS = [
  { key: "trl", code: "TRL", name: "Technology" },
  { key: "brl", code: "BRL", name: "Business" },
  { key: "crl", code: "CRL", name: "Customer" },
  { key: "frl", code: "FRL", name: "Funding" },
  { key: "ipr", code: "IPRL", name: "Intellectual property" },
  { key: "team", code: "TMRL", name: "Team" },
] as const;
export type DimensionKey = (typeof DIMENSIONS)[number]["key"];
export type Levels = Record<DimensionKey, number>;
export type KPI = {
  code: string;
  name: string;
  level: number;
  value?: string;
  unit?: string;
  source?: string;
};
export type StartupDetail = {
  slug: string;
  name: string;
  tagline: string;
  sector: string;
  country: string;
  region: string;
  city: string;
  founded_year: number | null;
  website: string;
  description: string;
  stage: string;
  last_round_on: string | null;
  pipeline_stage: PipelineStage;
  total_disclosed_usd: number;
  readiness: Levels & {
    assessor: string;
    assessed_on: string;
    confidence: Confidence;
    rationale: string;
  };
  levels: Levels;
  scores: {
    potential: number;
    readiness: number;
    ocean_impact: number;
    momentum: number;
    band: string;
    imbalance_penalty: number;
    readiness_spread: number;
    lagging_dimensions: DimensionKey[];
    ocean_areas_covered: string[];
    ocean_evidence_label: string;
  };
  funding_rounds: {
    round_type: string;
    announced_on: string;
    amount: number | null;
    currency: string | null;
    lead_investors: string;
    notes: string;
    source_url: string;
  }[];
  ocean_kpis: KPI[];
  notes: { id: string; body: string; author: string; created_at: string }[];
  sources: { url: string; title: string }[];
};
export type StartupSummary = StartupDetail;
export type Framework = {
  potential_weights: { readiness: number; ocean_impact: number; momentum: number };
  penalty_per_extra_level: number;
  max_healthy_spread: number;
  readiness_dimensions: {
    key: DimensionKey;
    code: string;
    name: string;
    weight: number;
    description: string;
    levels: { level: number; summary: string }[];
  }[];
  evidence_scale: { level: number; label: string }[];
  ocean_impact_areas: {
    code: string;
    name: string;
    orientation: string;
    kpis: { code: string; name: string; qualitative_only: boolean }[];
  }[];
};

// Search: same shape as the backend's POST /api/startups/search (LightRAG), so the mock
// client can be swapped for the real one without touching the pages.

/** A startup in the database that the search found. */
export type SearchMatch = StartupSummary & {
  /** 0-1, relative to the best match. */
  relevance: number;
  /** What led to it: knowledge-graph entities (backend) or query terms (mock). */
  matched: string[];
  /** The discovery agent's entry about it, if any. */
  entry: string | null;
};

/** A startup only the discovery agent knows about (not in the database yet). */
export type AgentEntryMatch = {
  entry: string;
  name: string;
  website: string | null;
  relevance: number;
  matched: string[];
  trl: number | null;
  brl: number | null;
  ocean_impact_readiness: number | null;
  investment_score: number | null;
  overall_confidence: number | null;
};

export type NaturalLanguageSearchResponse = {
  query: string;
  /** Most relevant first. */
  results: SearchMatch[];
  entries: AgentEntryMatch[];
};
