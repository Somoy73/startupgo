"""Domain models used by all scraper adapters."""

from __future__ import annotations

import hashlib
from dataclasses import dataclass, field
from typing import Literal

EvidenceConfidence = Literal["low", "medium", "high"]
EvidenceOrigin = Literal["explicit", "inferred", "unknown"]


@dataclass(slots=True)
class Evidence:
    """A claim with enough provenance for an analyst to verify it."""

    value: str
    source_url: str
    quote: str = ""
    confidence: EvidenceConfidence = "low"
    origin: EvidenceOrigin = "explicit"


@dataclass(slots=True)
class FundingEvidence:
    round_type: str | None = None
    amount: float | None = None
    currency: str | None = None
    announced_on: str | None = None
    investors: list[str] = field(default_factory=list)
    evidence: list[Evidence] = field(default_factory=list)


@dataclass(slots=True)
class ReadinessEvidence:
    trl: int | None = None
    brl: int | None = None
    trl_evidence: list[Evidence] = field(default_factory=list)
    brl_evidence: list[Evidence] = field(default_factory=list)


@dataclass(slots=True)
class StartupLead:
    """A normalized, source-independent candidate startup."""

    name: str
    source: str
    source_url: str
    tagline: str = ""
    description: str = ""
    website: str = ""
    country: str = ""
    city: str = ""
    sector: str = ""
    stage: str = ""
    latitude: float | None = None
    longitude: float | None = None
    external_id: str = ""

    def key(self) -> str:
        """Return a stable key used to remove duplicate leads."""

        value = self.website or self.source_url or self.name
        return hashlib.sha256(value.strip().lower().encode("utf-8")).hexdigest()[:16]


@dataclass(slots=True)
class StartupProfile:
    """Enriched startup profile produced from one or more public documents."""

    lead: StartupLead
    description: str = ""
    website_url: str = ""
    sector: str = ""
    funding: list[FundingEvidence] = field(default_factory=list)
    readiness: ReadinessEvidence = field(default_factory=ReadinessEvidence)
    evidence: list[Evidence] = field(default_factory=list)
