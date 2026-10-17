"""API response/request models."""

from typing import Annotated, ClassVar, Literal

from pydantic import BaseModel, Field, StringConstraints, model_validator

PipelineStage = Literal["sourced", "screening", "diligence", "term-sheet", "portfolio", "passed"]
FundingStage = Literal["pre-seed", "seed", "series-a", "series-b", "series-c+", "growth", "project-finance"]
Confidence = Literal["low", "medium", "high"]
PARTIAL_DATE = r"^\d{4}(-\d{2}(-\d{2})?)?$"


class Scores(BaseModel):
    readiness: float
    ocean_impact: float
    momentum: float
    potential: float
    band: str
    readiness_spread: int
    lagging_dimensions: list[str]
    ocean_evidence_label: str
    ocean_areas_covered: list[str]
    ocean_capped_by_oir: bool = False  # KPI evidence was lowered to what the agent's OIR supports
    ocean_evidence_known: bool = False  # False: no KPI evidence on record (ocean_impact 0 is "unknown")
    momentum_recency_known: bool = False  # False: no round date (recency counted 0)
    potential_coverage: float = 0.0  # share of the potential weights backed by data, 0-1
    ocean_evidence_known: bool = False  # False: no KPI evidence on record (ocean_impact 0 is "unknown")
    momentum_recency_known: bool = False  # False: no round date (recency counted 0)
    potential_coverage: float = 0.0  # share of the potential weights backed by data, 0-1


class Readiness(BaseModel):
    assessed_on: str
    assessor: str
    confidence: Confidence
    crl: int
    trl: int
    brl: int
    iprl: int
    tmrl: int
    frl: int
    rationale: str | None = None


class InvestmentCriterion(BaseModel):
    name: str
    score: int | None  # 1-5; None without facts
    confidence: float
    confidence_label: str
    fields_found: int
    fields_total: int
    reasons: list[str]


class InvestmentScores(BaseModel):
    """The agent's Investment Score Matrix (Modules/Agent/startup_agent/scoring.py): the agent's latest accepted assessment
    (source "agent"), else the same rubric and weights applied to the startup's facts in the database (source "facts")."""

    source: Literal["agent", "facts"]
    assessed_at: str | None  # the agent's assessment (UTC); None when scored from the facts
    trl: int | None
    brl: int | None
    ocean_impact_readiness: int | None  # 1-5
    investment_score: float | None  # weighted 1-5 over the criteria with facts
    investment_percent: float | None  # the same on 0-100
    overall_confidence: float
    criteria: list[InvestmentCriterion]


class StartupSummary(BaseModel):
    slug: str
    name: str
    tagline: str
    description: str
    sector: str
    country: str
    city: str | None
    stage: str
    pipeline_stage: PipelineStage
    assessed: bool = True  # False for a sourced startup the agent hasn't scored: its levels and scores are zero
    readiness: Readiness
    scores: Scores
    investment: InvestmentScores  # the agent's rubric: same numbers as the agent's entries
    total_disclosed_usd: float | None
    last_round_on: str | None
    founded_year: int | None = None
    created_at: str | None = None  # when StartupGo first found the startup (UTC)


class SearchFilters(BaseModel):
    """Structured filters applied to search and match results (same meaning as GET /api/startups).

    Agent-only entries have no profile, so only min_trl / min_brl apply to them; any other filter leaves them out.
    """

    sector: str | None = None
    country: str | None = None
    stage: str | None = None
    pipeline_stage: PipelineStage | None = None
    impact_area: str | None = Field(default=None, pattern=r"^[A-F]$")
    min_trl: int | None = Field(default=None, ge=1, le=9)
    min_brl: int | None = Field(default=None, ge=1, le=9)
    min_potential: float | None = Field(default=None, ge=0, le=100)


class NaturalLanguageSearchRequest(BaseModel):
    query: Annotated[str, StringConstraints(strip_whitespace=True, min_length=1, max_length=500)]
    filters: SearchFilters = Field(default_factory=SearchFilters)


class SearchMatch(StartupSummary):
    """A startup in the database that the search found."""

    relevance: float  # 0-1, relative to the best match
    matched: list[str]  # knowledge-graph entities that led to it
    entry: str | None  # the agent's entry about it, if any


class AgentEntryMatch(BaseModel):
    """A startup found only in the agent's entries (not in the database yet), with the agent's scores."""

    SCORES: ClassVar[tuple[str, ...]] = ("trl", "brl", "ocean_impact_readiness", "investment_score", "overall_confidence")

    entry: str
    name: str
    website: str | None
    relevance: float
    matched: list[str]
    trl: int | None = None
    brl: int | None = None
    ocean_impact_readiness: int | None = None
    investment_score: float | None = None
    overall_confidence: float | None = None


class NaturalLanguageSearchResponse(BaseModel):
    query: str
    results: list[SearchMatch]  # most relevant first
    entries: list[AgentEntryMatch]


class FundingRound(BaseModel):
    round_type: str
    amount: float | None
    currency: str | None
    amount_usd: float | None
    announced_on: str | None
    lead_investors: str | None
    notes: str | None
    source_url: str | None


class OceanKpiEvidence(BaseModel):
    kpi_code: str
    kpi_name: str
    area_code: str
    area_name: str
    evidence_level: int
    evidence_label: str
    claim: str
    source_url: str | None


class LevelDetail(BaseModel):
    dimension: str
    name: str
    level: int
    summary: str
    next_summary: str | None


class Source(BaseModel):
    title: str
    url: str


class Note(BaseModel):
    id: int
    author: str
    body: str
    created_at: str


class StartupDetail(StartupSummary):
    website: str | None
    levels: list[LevelDetail]
    ocean_kpis: list[OceanKpiEvidence]
    funding_rounds: list[FundingRound]
    sources: list[Source]
    notes: list[Note]


class PipelineUpdate(BaseModel):
    pipeline_stage: PipelineStage


class NoteCreate(BaseModel):
    body: str = Field(min_length=1, max_length=4000)
    author: str = Field(default="analyst", max_length=80)


class FilterOptions(BaseModel):
    sectors: list[str]
    countries: list[str]
    stages: list[str]
    pipeline_stages: list[str]
    impact_areas: list[dict]


# ---------------------------------------------------------------------------
# Assessment & creation inputs
# ---------------------------------------------------------------------------


class LevelsInput(BaseModel):
    crl: int = Field(ge=1, le=9)
    trl: int = Field(ge=1, le=9)
    brl: int = Field(ge=1, le=9)
    iprl: int = Field(ge=1, le=9)
    tmrl: int = Field(ge=1, le=9)
    frl: int = Field(ge=1, le=9)


class KpiLevel(BaseModel):
    kpi_code: str = Field(pattern=r"^[A-F][1-6]$")
    evidence_level: int = Field(ge=0, le=4)


class KpiEvidenceInput(KpiLevel):
    claim: str = Field(default="", max_length=500)
    source_url: str | None = Field(default=None, max_length=500)

    @model_validator(mode="after")
    def claim_required_for_evidence(self) -> "KpiEvidenceInput":
        if self.evidence_level > 0 and not self.claim.strip():
            raise ValueError(f"{self.kpi_code}: a claim is required when evidence_level > 0")
        return self


class AssessmentCreate(LevelsInput):
    assessor: str = Field(min_length=1, max_length=80)
    confidence: Confidence
    rationale: str | None = Field(default=None, max_length=2000)
    ocean_kpis: list[KpiEvidenceInput] = Field(default_factory=list)


class FundingRoundInput(BaseModel):
    round_type: str = Field(min_length=1, max_length=40)
    amount: float | None = Field(default=None, ge=0)
    currency: str | None = Field(default=None, pattern=r"^[A-Z]{3}$")
    announced_on: str | None = Field(default=None, pattern=PARTIAL_DATE)
    lead_investors: str | None = Field(default=None, max_length=200)


class StartupCreate(BaseModel):
    name: str = Field(min_length=1, max_length=120)
    tagline: str = Field(min_length=1, max_length=200)
    description: str = Field(min_length=1, max_length=4000)
    sector: str = Field(min_length=1, max_length=80)
    country: str = Field(min_length=1, max_length=80)
    city: str | None = Field(default=None, max_length=80)
    founded_year: int | None = Field(default=None, ge=1900, le=2100)
    website: str | None = Field(default=None, max_length=300)
    stage: FundingStage
    funding_round: FundingRoundInput | None = None
    assessment: AssessmentCreate


class ScorePreviewRequest(LevelsInput):
    ocean_kpis: list[KpiLevel] = Field(default_factory=list)
    stage: str
    last_round_on: str | None = Field(default=None, pattern=PARTIAL_DATE)


# --- Success-prediction features (Modules/DataAPIs/features.py) ---


class FeatureDefinition(BaseModel):
    name: str
    feature_group: str
    description: str
    unit: str | None
    importance: Literal["high", "medium", "low"] | None
    origin: str
    sources: str | None


class FeatureValue(BaseModel):
    name: str
    feature_group: str
    value: float | None
    text: str | None
    unit: str | None
    importance: str | None
    evidence: dict | list | None


class StartupFeatures(BaseModel):
    slug: str
    as_of: str | None
    features: list[FeatureValue]
    missing: list[str] = Field(description="Catalogue features with no value: unknown, not zero")


class FundingEvent(BaseModel):
    """A round, grant or raised total from one source (a facts row: equity_rounds, grants, total_raised)."""

    event_date: str | None
    source_name: str
    event_type: str  # announced_round, priced_round (UK SH01), form_d, eu_grant, grant, aggregate
    round_label: str | None
    amount: float | None
    currency: str | None
    price_per_share: float | None
    investor_count: int | None
    source_url: str | None
    status: str  # verified, claimed, inferred
    confidence: float
    details: dict | None


class Venture(BaseModel):
    company_name: str
    company_number: str | None
    company_status: str | None
    role: str | None
    appointed_on: str | None
    resigned_on: str | None
    before_startup: bool | None


class Person(BaseModel):
    name: str
    role: str
    is_founder: bool  # else a current board member
    appointed_on: str | None
    active: bool | None  # founders: still with the company
    source_name: str
    education: list[dict] | None = None  # degree level and school, from PDL; never scored for prestige
    ventures: list[Venture]


class InvestorLink(BaseModel):
    name: str
    kind: str | None
    tier_score: float | None
    role: str
    rounds: int
    first_seen: str | None


class Peer(BaseModel):
    slug: str | None
    name: str
    sector: str | None
    similarity: float


# --- EU and ocean-specific sources (Modules/DataAPIs/ingest_eu.py) ---


class EuGrant(BaseModel):
    project_id: str
    programme: str | None  # framework and acronym, e.g. "H2020 UCUP"
    role: str | None
    ec_contribution: float | None
    currency: str | None
    start_date: str | None
    is_eic: bool
    is_mission_ocean: bool
    url: str | None


class Patent(BaseModel):
    publication_number: str
    title: str
    url: str | None
    priority_date: str | None
    legal_status: str | None
    granted: str | None
    ocean_groups: list[str]


class BlueInvestProfile(BaseModel):
    other_id: int
    name: str
    summary: str | None
    trl: int | None
    sector: str | None
    company: str | None
    country: str | None
    funding_sought_eur: float | None
    website: str | None
    matched_slug: str | None
    url: str | None


class ExternalPeer(BaseModel):
    source: str
    external_id: str | None  # BlueInvest id of the lead, when its project name finds one
    name: str
    similarity: float
    trl: int | None
    sector: str | None
    website: str | None


# ---------------------------------------------------------------------------
# Agent research jobs (app/research.py, Modules/Agent)
# ---------------------------------------------------------------------------

JobStatus = Literal["queued", "running", "done", "error"]


class ResearchRequest(BaseModel):
    """Research a database startup (slug) or a new one (name + website); urls are extra pages to read."""

    slug: str | None = None
    name: str | None = Field(default=None, min_length=1, max_length=120)
    website: str | None = Field(default=None, pattern=r"^https?://\S+$", max_length=300)
    business_id: str | None = Field(default=None, max_length=40)
    urls: list[Annotated[str, StringConstraints(pattern=r"^https?://\S+$", max_length=500)]] = Field(default_factory=list, max_length=5)

    @model_validator(mode="after")
    def _target(self) -> "ResearchRequest":
        if not self.slug and not (self.name and self.website):
            raise ValueError("give a slug, or a name and a website")
        return self


class ResearchJob(BaseModel):
    id: int
    status: JobStatus
    name: str
    website: str
    slug: str | None  # the startup, once known (a new startup gets one when the judge accepts it)
    business_id: str | None
    urls: list[str]
    refresh: bool  # researched again, ignoring the agent's cache: the last score had no evidence for TRL or BRL
    created_at: str
    started_at: str | None
    finished_at: str | None
    result: dict | None  # scores, judge review and whether it was stored
    error: str | None


ScrapeUrl = Annotated[str, StringConstraints(pattern=r"^https?://\S+$", max_length=1000)]
ScrapeMode = Literal["general", "startups", "funding_calls", "projects", "funding_rounds", "company", "document"]


class ScrapeSource(BaseModel):
    """One source for the scrape agent: what to get, where (no urls: it searches the web), and its focus prompt."""

    goal: str = Field(min_length=3, max_length=1500)
    urls: list[ScrapeUrl] = Field(default_factory=list, max_length=10)
    follow_links: bool = False  # also read the links on those pages that match the goal
    max_pages: int = Field(default=8, ge=1, le=20)
    mode: ScrapeMode = "general"  # Modules/Agent/prompts/scrape/<mode>.md
    label: str = Field(default="", max_length=80)  # the source's name in the merged result


class ScrapeRequest(BaseModel):
    """Several sources in ``sources`` (read in turn, merged into one result), or one given by goal and urls."""

    sources: list[ScrapeSource] = Field(default_factory=list, max_length=8)
    goal: str | None = Field(default=None, min_length=3, max_length=1500)
    urls: list[ScrapeUrl] = Field(default_factory=list, max_length=10)
    follow_links: bool = False
    max_pages: int = Field(default=8, ge=1, le=20)
    mode: ScrapeMode = "general"
    stealth: bool = True  # render pages in the stealth Chrome; False = plain HTTP
    llm: str | None = Field(default=None, max_length=40)  # model profile, e.g. "nvidia" or "gemini"; None = the default

    @model_validator(mode="after")
    def _one_source_at_least(self) -> "ScrapeRequest":
        if not self.sources:
            if not self.goal:
                raise ValueError("give sources, or a goal")
            self.sources = [ScrapeSource(goal=self.goal, urls=self.urls, follow_links=self.follow_links, max_pages=self.max_pages, mode=self.mode)]
        return self


class ScrapeJob(BaseModel):
    id: int
    status: JobStatus
    sources: list[ScrapeSource]
    stealth: bool
    llm: str | None
    created_at: str
    started_at: str | None
    finished_at: str | None
    progress: list[str]  # what the agent did so far, in order
    result: dict | None  # summary, groups, records (each with its quote check and source), gaps, sources, notices, model, usage
    error: str | None


class ScrapedAttribute(BaseModel):
    name: str = Field(max_length=200)
    value: str = Field(max_length=2000)


class ScrapedRecord(BaseModel):
    """A record from a scrape result, as the agent returned it."""

    kind: str = Field(default="startup", max_length=40)
    title: str = Field(min_length=1, max_length=200)
    details: str = Field(default="", max_length=4000)
    website: str = Field(default="", max_length=300)
    attributes: list[ScrapedAttribute] = Field(default_factory=list, max_length=60)
    source_url: str = Field(default="", max_length=1000)
    quote: str = Field(default="", max_length=2000)
    evidence: Literal["page", "transcript", "unverified"] = "unverified"
    self_reported: bool = False
    group: str = Field(default="", max_length=80)


class ScrapedStartup(BaseModel):
    """Add a scraped startup to the database; ``website`` when the record has none (or to correct it)."""

    record: ScrapedRecord
    website: str | None = Field(default=None, pattern=r"^(https?://)?[^\s/]+\.[^\s]+$", max_length=300)


class ScrapedStartupAdded(BaseModel):
    slug: str
    name: str
    status: Literal["created", "promoted", "exists"]  # promoted: a BlueInvest candidate became a startup


class ScrapeModel(BaseModel):
    name: str  # the [llm.<name>] profile
    provider: str
    model: str
    multimodal: bool  # reads images (and, for Gemini, scanned PDFs)
    key_set: bool  # its API key is in Modules/Agent/.env


class ScrapeAgentInfo(BaseModel):
    """The models the scraper can use (Modules/Agent/config.toml), the default one, and whether it searches the web."""

    default: str
    models: list[ScrapeModel]
    web_search: bool  # finds pages itself when no URL is given


class AgentAssessment(BaseModel):
    """The agent's latest judge-approved assessment of a startup (assessments row, engine 'agent')."""

    assessed_at: str  # UTC
    judge_status: str
    trl: int
    brl: int
    oir: int | None  # Ocean Impact Readiness 1-5
    investment_score: float | None  # agent's 1-5 score
    overall_confidence: float | None


class StartupResearch(BaseModel):
    slug: str
    has_agent_assessment: bool
    agent: AgentAssessment | None
    researched_at: str | None  # last agent research run (UTC), whatever the judge decided; researched again 30 days later
    job: ResearchJob | None  # latest research job since the Backend started


# ---------------------------------------------------------------------------
# Matching graph: N-hop subgraphs of the search's knowledge graph (Modules/Search graph.py)
# ---------------------------------------------------------------------------


class GraphNodeOut(BaseModel):
    id: str  # entity name
    type: str | None
    description: str
    hop: int
    startups: list[str]  # "startup:<slug>" or "entry:<agent entry id>"


class GraphEdgeOut(BaseModel):
    source: str
    target: str
    keywords: str
    description: str
    weight: float


class GraphResponse(BaseModel):
    seeds: list[str]
    nodes: list[GraphNodeOut]
    edges: list[GraphEdgeOut]
    truncated: bool
    results: list[SearchMatch]  # database startups the graph reaches, best first
    entries: list[AgentEntryMatch]


class ThesisGraphRequest(BaseModel):
    thesis: Annotated[str, StringConstraints(strip_whitespace=True, min_length=1, max_length=1000)]
    hops: int = Field(default=1, ge=0, le=3)
    max_nodes: int = Field(default=150, ge=1, le=500)
    seeds: int = Field(default=10, ge=1, le=40)
    filters: SearchFilters = Field(default_factory=SearchFilters)


# ---------------------------------------------------------------------------
# Investment memo: one document per startup, assembled from the database (app/memo.py)
# ---------------------------------------------------------------------------


class MemoRecommendation(BaseModel):
    verdict: str  # Advance to due diligence | Take a first call | Monitor | Pass for now | Research first
    tone: Literal["positive", "neutral", "caution"]
    rationale: str


class MemoNextStep(BaseModel):
    action: str
    reason: str
    resource: str | None


class MemoAssessment(BaseModel):
    engine: str  # seed-estimate | analyst | startupgo-pipeline | agent
    assessed_on: str
    confidence: Confidence
    rationale: str | None
    judge_status: str | None


class InvestmentMemo(BaseModel):
    generated_at: str  # UTC
    startup: StartupDetail
    assessment: MemoAssessment | None  # None until the startup is assessed
    recommendation: MemoRecommendation
    highlights: list[str]
    risks: list[str]
    questions: list[str]  # due-diligence questions for the first call (the agent's data gaps)
    next_steps: list[MemoNextStep]
    founders: list[Person]
    investors: list[InvestorLink]
    funding: list[FundingEvent]
    grants: list[EuGrant]
    patents: list[Patent]
    peers: list[Peer]
