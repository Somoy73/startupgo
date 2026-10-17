export const PIPELINE_STAGES = [
  "sourced",
  "screening",
  "diligence",
  "term-sheet",
  "invested",
  "passed",
] as const;
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
  created_at: string | null;
  growth_speed: number | null;
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
