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

export type ResearchJob = {
  id: number;
  status: "queued" | "running" | "done" | "error";
  slug: string | null;
  error: string | null;
  result: Record<string, unknown> | null;
};

/** A source's focus prompt (Modules/Agent/prompts/scrape/<mode>.md). */
export type ScrapeMode =
  | "general"
  | "startups"
  | "funding_calls"
  | "projects"
  | "funding_rounds"
  | "company"
  | "document";

/** One source of a scrape job: what to get, where (no URLs: the agent searches the web), and its focus. */
export type ScrapeTarget = {
  goal: string;
  urls: string[];
  follow_links: boolean;
  max_pages: number;
  mode: ScrapeMode;
  label: string;
};

export type ScrapeRequest = {
  sources: ScrapeTarget[];
  stealth: boolean;
  /** Model profile from GET /agent-scrape/info; omitted = the default. */
  llm?: string;
};

/** How well a record's quote was checked: found on the page, found in the model's text of a PDF/image, or not found. */
export type ScrapeEvidence = "page" | "transcript" | "unverified";

export type ScrapeRecordKind =
  | "startup"
  | "company"
  | "funding_call"
  | "project"
  | "funding_round"
  | "investor"
  | "figure"
  | "other";

export type ScrapeRecord = {
  kind: ScrapeRecordKind;
  title: string;
  details: string;
  /** The record's own website, "" when the source doesn't give it. */
  website: string;
  attributes: { name: string; value: string }[];
  source_url: string;
  quote: string;
  evidence: ScrapeEvidence;
  /** Read on the record's own website: the company's claim, not independent evidence. */
  self_reported: boolean;
  /** The source (job source label) the record came from. */
  group: string;
  /** Other sources of this job that describe the same thing. */
  also_in: string[];
};

export type ScrapeSource = {
  url: string;
  kind: "page" | "pdf" | "image";
  status: "read" | "empty" | "skipped" | "error";
  detail: string;
  group: string;
};

export type ScrapeGroup = {
  label: string;
  goal: string;
  mode: ScrapeMode;
  summary: string;
  records: number;
  /** Why this source gave nothing, when it failed while the others went on. */
  error: string | null;
};

export type ScrapeResult = {
  goal: string;
  summary: string;
  groups: ScrapeGroup[];
  records: ScrapeRecord[];
  gaps: string[];
  sources: ScrapeSource[];
  notices: string[];
  model: string;
  usage: string;
};

export type ScrapeJob = {
  id: number;
  status: "queued" | "running" | "done" | "error";
  sources: ScrapeTarget[];
  created_at: string;
  progress: string[];
  result: ScrapeResult | null;
  error: string | null;
};

/** A scraped startup in the database: created, promoted from a BlueInvest lead, or already there (evidence added). */
export type ScrapedStartupAdded = { slug: string; name: string; status: "created" | "promoted" | "exists" };

/** A model the scraper can use: multimodal models read images (Gemini also scanned PDFs). */
export type ScrapeModel = {
  name: string;
  provider: string;
  model: string;
  multimodal: boolean;
  /** Its API key is in Modules/Agent/.env. */
  key_set: boolean;
};

export type ScrapeAgentInfo = { default: string; models: ScrapeModel[]; web_search: boolean };

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
