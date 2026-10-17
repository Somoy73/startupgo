"""API response/request models."""

from typing import Literal

from pydantic import BaseModel, Field

PipelineStage = Literal["sourced", "screening", "diligence", "term-sheet", "portfolio", "passed"]


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
    confidence: Literal["low", "medium", "high"]
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
    sector: str
    country: str
    city: str | None
    stage: str
    pipeline_stage: PipelineStage
    readiness: Readiness
    scores: Scores
    total_disclosed_usd: float | None
    last_round_on: str | None


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
    description: str
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


# --- Success-prediction features (DataAPIs/features.py) ---


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
    event_date: str
    source_name: str
    event_type: str
    round_label: str | None
    amount: float | None
    currency: str | None
    share_class: str | None
    shares_allotted: int | None
    price_per_share: float | None
    total_shares_after: int | None
    implied_post_money: float | None
    investor_count: int | None
    source_url: str | None
    match_confidence: str
    details: dict | None


class Venture(BaseModel):
    company_name: str
    company_number: str
    company_status: str | None
    role: str | None
    appointed_on: str | None
    resigned_on: str | None
    before_startup: bool | None


class Person(BaseModel):
    name: str
    role: str
    is_founder: bool
    appointed_on: str | None
    resigned_on: str | None
    nationality: str | None
    source_name: str
    ventures: list[Venture]


class InvestorLink(BaseModel):
    name: str
    kind: str | None
    tier_score: float | None
    role: str
    rounds: int
    first_seen: str | None


class Peer(BaseModel):
    slug: str
    name: str
    sector: str
    similarity: float
    shared_tags: list[str]
