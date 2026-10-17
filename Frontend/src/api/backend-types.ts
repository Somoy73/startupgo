// Response shapes of the FastAPI backend (Backend/app/schemas.py). Separate from ./types,
// which describes the mock data the other pages still use.

export type BackendPipelineStage =
  "sourced" | "screening" | "diligence" | "term-sheet" | "portfolio" | "passed";

export type Confidence = "low" | "medium" | "high";

export type Readiness = {
  assessed_on: string;
  assessor: string;
  confidence: Confidence;
  crl: number;
  trl: number;
  brl: number;
  iprl: number;
  tmrl: number;
  frl: number;
  rationale: string | null;
};

export type Scores = {
  readiness: number;
  ocean_impact: number;
  momentum: number;
  imbalance_penalty: number;
  potential: number;
  band: string;
  readiness_spread: number;
  /** Upper-case KTH codes, e.g. "TRL". */
  lagging_dimensions: string[];
  ocean_evidence_label: string;
  ocean_areas_covered: string[];
};

/** One KTH IRL dimension at its current level, with what the next level requires. */
export type LevelDetail = {
  /** KTH code, e.g. "TRL". */
  dimension: string;
  name: string;
  level: number;
  summary: string;
  next_summary: string | null;
};

export type OceanKpiEvidence = {
  kpi_code: string;
  kpi_name: string;
  area_code: string;
  area_name: string;
  evidence_level: number;
  evidence_label: string;
  claim: string;
  source_url: string | null;
};

export type FundingRound = {
  round_type: string;
  amount: number | null;
  currency: string | null;
  amount_usd: number | null;
  announced_on: string | null;
  lead_investors: string | null;
  notes: string | null;
  source_url: string | null;
};

export type Source = { title: string; url: string };

export type Note = { id: number; author: string; body: string; created_at: string };

export type StartupSummary = {
  slug: string;
  name: string;
  tagline: string;
  description: string;
  sector: string;
  country: string;
  city: string | null;
  stage: string;
  pipeline_stage: BackendPipelineStage;
  readiness: Readiness;
  scores: Scores;
  total_disclosed_usd: number | null;
  last_round_on: string | null;
};

export type StartupDetail = StartupSummary & {
  founded_year: number | null;
  website: string | null;
  levels: LevelDetail[];
  ocean_kpis: OceanKpiEvidence[];
  funding_rounds: FundingRound[];
  sources: Source[];
  notes: Note[];
};

/** The six KTH IRL dimensions, keyed as in Readiness. */
export const KTH_DIMENSIONS = [
  { key: "trl", code: "TRL", name: "Technology" },
  { key: "brl", code: "BRL", name: "Business" },
  { key: "crl", code: "CRL", name: "Customer" },
  { key: "frl", code: "FRL", name: "Funding" },
  { key: "iprl", code: "IPRL", name: "Intellectual property" },
  { key: "tmrl", code: "TMRL", name: "Team" },
] as const;
export type KthKey = (typeof KTH_DIMENSIONS)[number]["key"];

export const BACKEND_PIPELINE_STAGES: readonly BackendPipelineStage[] = [
  "sourced",
  "screening",
  "diligence",
  "term-sheet",
  "portfolio",
  "passed",
];

/** A database startup the natural-language search found. */
export type SearchMatch = StartupSummary & {
  /** 0-1, relative to the best match. */
  relevance: number;
  /** Knowledge-graph entities that led to it. */
  matched: string[];
  /** The agent's entry about it, if any. */
  entry: string | null;
};

/** A startup found only in the agent's entries (not in the database yet), with the agent's scores. */
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

export type OceanImpactArea = { code: string; name: string };

/** GET /api/frameworks, the parts the frontend reads. */
export type Frameworks = {
  ocean_impact_areas: OceanImpactArea[];
  /** Share of each score in the investment potential (sums to 1). */
  potential_weights: { readiness: number; ocean_impact: number; momentum: number };
};

/** A round, grant or raised total from one source. The same round can appear once per source. */
export type FundingEvent = {
  event_date: string | null;
  source_name: string;
  /** announced_round, priced_round (UK SH01), form_d, eu_grant, grant, aggregate */
  event_type: string;
  round_label: string | null;
  amount: number | null;
  currency: string | null;
  price_per_share: number | null;
  investor_count: number | null;
  source_url: string | null;
  /** verified, claimed, inferred */
  status: string;
  confidence: number;
  details: Record<string, unknown> | null;
};

/** A similar startup (weighted tag overlap); slug is null when it isn't in the database. */
export type Peer = { slug: string | null; name: string; sector: string | null; similarity: number };
