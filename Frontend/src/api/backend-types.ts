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
