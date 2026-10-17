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
  potential: number;
  band: string;
  readiness_spread: number;
  /** Upper-case KTH codes, e.g. "TRL". */
  lagging_dimensions: string[];
  ocean_evidence_label: string;
  ocean_areas_covered: string[];
  ocean_capped_by_oir?: boolean;
  ocean_evidence_known?: boolean;
  momentum_recency_known?: boolean;
  potential_coverage?: number;
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
  /** False for a sourced startup the research agent hasn't scored yet: its levels and scores are zero. */
  assessed: boolean;
  readiness: Readiness;
  scores: Scores;
  /** The agent's Investment Score Matrix (its latest accepted assessment, else its rubric on the facts). */
  investment?: InvestmentScores;
  total_disclosed_usd: number | null;
  last_round_on: string | null;
  founded_year?: number | null;
  /** When StartupGo first found the startup (UTC). */
  created_at?: string | null;
};

export type StartupDetail = StartupSummary & {
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
export type Frameworks = { ocean_impact_areas: OceanImpactArea[] };

export type ResearchJob = {
  id: number;
  status: "queued" | "running" | "done" | "error";
  slug: string | null;
  error: string | null;
  result: Record<string, unknown> | null;
};

export type InvestmentCriterion = {
  name: string;
  /** 1-5; null without facts. */
  score: number | null;
  confidence: number;
  confidence_label: string;
  fields_found: number;
  fields_total: number;
  reasons: string[];
};

export type InvestmentScores = {
  source: "agent" | "facts";
  assessed_at: string | null;
  trl: number | null;
  brl: number | null;
  ocean_impact_readiness: number | null;
  /** Weighted 1-5 over the criteria with facts. */
  investment_score: number | null;
  investment_percent: number | null;
  overall_confidence: number;
  criteria: InvestmentCriterion[];
};

export type Person = {
  name: string;
  role: string;
  is_founder: boolean;
  appointed_on: string | null;
  active: boolean | null;
  source_name: string;
  ventures: { company_name: string; company_status: string | null; role: string | null; before_startup: boolean | null }[];
};

export type InvestorLink = {
  name: string;
  kind: string | null;
  tier_score: number | null;
  role: string;
  rounds: number;
  first_seen: string | null;
};

export type FundingEvent = {
  event_date: string | null;
  source_name: string;
  event_type: string;
  round_label: string | null;
  amount: number | null;
  currency: string | null;
  source_url: string | null;
  status: string;
};

export type EuGrant = {
  project_id: string;
  programme: string | null;
  role: string | null;
  ec_contribution: number | null;
  currency: string | null;
  start_date: string | null;
  is_eic: boolean;
  is_mission_ocean: boolean;
  url: string | null;
};

export type Patent = {
  publication_number: string;
  title: string;
  url: string | null;
  priority_date: string | null;
  legal_status: string | null;
  granted: string | null;
  ocean_groups: string[];
};

export type Peer = { slug: string | null; name: string; sector: string | null; similarity: number };

/** GET /api/startups/{slug}/memo: the one-click investment memo (Backend/app/memo.py). */
export type InvestmentMemo = {
  generated_at: string;
  startup: StartupDetail;
  assessment: {
    engine: string;
    assessed_on: string;
    confidence: Confidence;
    rationale: string | null;
    judge_status: string | null;
  } | null;
  recommendation: {
    verdict: string;
    tone: "positive" | "neutral" | "caution";
    rationale: string;
    /** The recommendation's reasons, one per bullet. */
    points: string[];
  };
  /** Executive summary: paragraphs justifying the recommendation. */
  summary: string[];
  highlights: string[];
  risks: string[];
  questions: string[];
  next_steps: { action: string; reason: string; resource: string | null }[];
  founders: Person[];
  investors: InvestorLink[];
  funding: FundingEvent[];
  grants: EuGrant[];
  patents: Patent[];
  peers: Peer[];
};
