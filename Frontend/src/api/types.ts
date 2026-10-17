// Mirrors Backend/app/schemas.py

export type PipelineStage = "sourced" | "screening" | "diligence" | "term-sheet" | "portfolio" | "passed";

export const PIPELINE_STAGES: PipelineStage[] = [
  "sourced",
  "screening",
  "diligence",
  "term-sheet",
  "portfolio",
  "passed",
];

export type FundingStage = "pre-seed" | "seed" | "series-a" | "series-b" | "series-c+" | "growth" | "project-finance";

export const FUNDING_STAGES: FundingStage[] = [
  "pre-seed",
  "seed",
  "series-a",
  "series-b",
  "series-c+",
  "growth",
  "project-finance",
];

export type Confidence = "low" | "medium" | "high";

export type DimensionKey = "crl" | "trl" | "brl" | "iprl" | "tmrl" | "frl";

export const DIMENSIONS: { key: DimensionKey; code: string; name: string }[] = [
  { key: "crl", code: "CRL", name: "Customer" },
  { key: "trl", code: "TRL", name: "Technology" },
  { key: "brl", code: "BRL", name: "Business model" },
  { key: "iprl", code: "IPRL", name: "IP" },
  { key: "tmrl", code: "TMRL", name: "Team" },
  { key: "frl", code: "FRL", name: "Funding" },
];

export interface Scores {
  readiness: number;
  ocean_impact: number;
  momentum: number;
  imbalance_penalty: number;
  potential: number;
  band: "Strong" | "Promising" | "Watch" | "Early";
  readiness_spread: number;
  lagging_dimensions: string[];
  ocean_evidence_label: string;
  ocean_areas_covered: string[];
}

export interface Readiness extends Record<DimensionKey, number> {
  assessed_on: string;
  assessor: string;
  confidence: Confidence;
  rationale: string | null;
}

export interface StartupSummary {
  slug: string;
  name: string;
  tagline: string;
  description: string;
  sector: string;
  country: string;
  city: string | null;
  stage: string;
  pipeline_stage: PipelineStage;
  readiness: Readiness;
  scores: Scores;
  total_disclosed_usd: number | null;
  last_round_on: string | null;
}

export interface FundingRound {
  round_type: string;
  amount: number | null;
  currency: string | null;
  amount_usd: number | null;
  announced_on: string | null;
  lead_investors: string | null;
  notes: string | null;
  source_url: string | null;
}

export interface OceanKpiEvidence {
  kpi_code: string;
  kpi_name: string;
  area_code: string;
  area_name: string;
  evidence_level: number;
  evidence_label: string;
  claim: string;
  source_url: string | null;
}

export interface LevelDetail {
  dimension: string;
  name: string;
  level: number;
  summary: string;
  next_summary: string | null;
}

export interface Note {
  id: number;
  author: string;
  body: string;
  created_at: string;
}

export interface StartupDetail extends StartupSummary {
  founded_year: number | null;
  website: string | null;
  levels: LevelDetail[];
  ocean_kpis: OceanKpiEvidence[];
  funding_rounds: FundingRound[];
  sources: { title: string; url: string }[];
  notes: Note[];
}

export interface Frameworks {
  readiness_dimensions: {
    code: string;
    name: string;
    description: string;
    weight: number;
    levels: { level: number; summary: string }[];
  }[];
  ocean_impact_areas: {
    code: string;
    name: string;
    orientation: string;
    kpis: { code: string; name: string; qualitative_only: number }[];
  }[];
  evidence_scale: { level: number; label: string }[];
  potential_weights: { readiness: number; ocean_impact: number; momentum: number };
  max_healthy_spread: number;
  penalty_per_extra_level: number;
}

// ---------- Search ----------

/** Wire format of the search filters (SearchFilters in schemas.py). */
export interface ApiSearchFilters {
  stages: string[];
  sectors: string[];
  countries: string[];
  regions: string[];
  impact_areas: string[];
  pipeline: string[];
  /** 0 means no minimum. */
  min_levels: Record<DimensionKey, number>;
  /** All must appear. */
  keywords: string[];
  /** At least one must appear. */
  any_keywords: string[];
}

/** POST /api/search: a natural-language `query` or explicit `filters` (edited chips and dropdowns). */
export type SearchRequest = { query: string } | { filters: ApiSearchFilters };

export interface SearchResponse {
  query: string | null;
  /** Filters the search applied (shown as chips), or null if it produced none. */
  filters: ApiSearchFilters | null;
  notice: string | null;
  startups: StartupSummary[];
}

// ---------- Write models ----------

export type Levels = Record<DimensionKey, number>;

export interface KpiEvidenceInput {
  kpi_code: string;
  evidence_level: number;
  claim: string;
  source_url: string | null;
}

export interface AssessmentInput extends Levels {
  assessor: string;
  confidence: Confidence;
  rationale: string | null;
  ocean_kpis: KpiEvidenceInput[];
}

export interface FundingRoundInput {
  round_type: string;
  amount: number | null;
  currency: string | null;
  announced_on: string | null;
  lead_investors: string | null;
}

export interface StartupInput {
  name: string;
  tagline: string;
  description: string;
  sector: string;
  country: string;
  city: string | null;
  founded_year: number | null;
  website: string | null;
  stage: FundingStage;
  funding_round: FundingRoundInput | null;
  assessment: AssessmentInput;
}

export interface ScorePreviewInput extends Levels {
  ocean_kpis: { kpi_code: string; evidence_level: number }[];
  stage: string;
  last_round_on: string | null;
}
