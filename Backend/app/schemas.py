"""API response/request models."""

from typing import Annotated, ClassVar, Literal

from pydantic import BaseModel, ConfigDict, Field, StringConstraints, model_validator

PipelineStage = Literal["sourced", "screening", "diligence", "term-sheet", "portfolio", "passed"]
FundingStage = Literal["pre-seed", "seed", "series-a", "series-b", "series-c+", "growth", "project-finance"]
Confidence = Literal["low", "medium", "high"]
PARTIAL_DATE = r"^\d{4}(-\d{2}(-\d{2})?)?$"


class Scores(BaseModel):
    readiness: float
    ocean_impact: float
    momentum: float
    imbalance_penalty: float
    potential: float
    band: str
    readiness_spread: int
    lagging_dimensions: list[str]
    ocean_evidence_label: str
    ocean_areas_covered: list[str]


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
    readiness: Readiness
    scores: Scores
    total_disclosed_usd: float | None
    last_round_on: str | None


class NaturalLanguageSearchRequest(BaseModel):
    query: Annotated[str, StringConstraints(strip_whitespace=True, min_length=1, max_length=500)]


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
    founded_year: int | None
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


# ---------------------------------------------------------------------------
# Search
# ---------------------------------------------------------------------------

Region = Literal["europe", "north-america", "latin-america", "asia", "africa", "oceania", "nordics", "baltics"]
ImpactArea = Literal["A", "B", "C", "D", "E", "F"]


class MinLevels(BaseModel):
    """Minimum KTH readiness level per dimension, 1-9; 0 means no minimum."""

    model_config = ConfigDict(extra="forbid")

    crl: int = Field(ge=0, le=9)
    trl: int = Field(ge=0, le=9)
    brl: int = Field(ge=0, le=9)
    iprl: int = Field(ge=0, le=9)
    tmrl: int = Field(ge=0, le=9)
    frl: int = Field(ge=0, le=9)


class SearchFilters(BaseModel):
    """Structured filters. Empty lists and 0 levels mean no constraint; lists OR within, AND across."""

    model_config = ConfigDict(extra="forbid")

    stages: list[FundingStage]
    sectors: list[str]
    countries: list[str]
    regions: list[Region]
    impact_areas: list[ImpactArea]
    pipeline: list[PipelineStage]
    min_levels: MinLevels
    keywords: list[str] = Field(description="All must appear in the startup's text")
    any_keywords: list[str] = Field(description="At least one must appear in the startup's text")


class SearchRequest(BaseModel):
    """Either a natural-language `query` or explicit `filters` (edited chips and dropdowns)."""

    model_config = ConfigDict(extra="forbid")

    query: str | None = Field(default=None, min_length=1, max_length=300)
    filters: SearchFilters | None = None

    @model_validator(mode="after")
    def exactly_one_input(self) -> "SearchRequest":
        if (self.query is None) == (self.filters is None):
            raise ValueError("send exactly one of 'query' or 'filters'")
        return self


class SearchResponse(BaseModel):
    query: str | None
    # The filters the search applied, shown as chips; None if it didn't produce any.
    filters: SearchFilters | None
    notice: str | None
    startups: list[StartupSummary]
