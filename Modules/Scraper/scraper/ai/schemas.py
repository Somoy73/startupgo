"""Validated response objects expected from the enrichment model."""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Literal

EvidenceConfidence = Literal["low", "medium", "high"]
EvidenceOrigin = Literal["explicit", "inferred", "unknown"]


@dataclass(slots=True)
class EvidenceResponse:
    value: str
    source_url: str
    quote: str = ""
    confidence: EvidenceConfidence = "low"
    origin: EvidenceOrigin = "explicit"

    @classmethod
    def from_dict(cls, data: dict) -> "EvidenceResponse":
        return cls(**data)


@dataclass(slots=True)
class FundingResponse:
    round_type: str | None = None
    amount: float | None = None
    currency: str | None = None
    announced_on: str | None = None
    investors: list[str] = field(default_factory=list)
    evidence: list[EvidenceResponse] = field(default_factory=list)

    @classmethod
    def from_dict(cls, data: dict) -> "FundingResponse":
        return cls(
            round_type=data.get("round_type"),
            amount=data.get("amount"),
            currency=data.get("currency"),
            announced_on=data.get("announced_on"),
            investors=data.get("investors", []),
            evidence=[EvidenceResponse.from_dict(item) for item in data.get("evidence", [])],
        )


@dataclass(slots=True)
class ReadinessResponse:
    trl: int | None = None
    brl: int | None = None
    trl_evidence: list[EvidenceResponse] = field(default_factory=list)
    brl_evidence: list[EvidenceResponse] = field(default_factory=list)

    @classmethod
    def from_dict(cls, data: dict) -> "ReadinessResponse":
        return cls(
            trl=data.get("trl"),
            brl=data.get("brl"),
            trl_evidence=[EvidenceResponse.from_dict(item) for item in data.get("trl_evidence", [])],
            brl_evidence=[EvidenceResponse.from_dict(item) for item in data.get("brl_evidence", [])],
        )


@dataclass(slots=True)
class StartupEnrichmentResponse:
    description: str
    website_url: str | None
    sector: str
    funding: list[FundingResponse]
    readiness: ReadinessResponse
    evidence: list[EvidenceResponse]

    @classmethod
    def from_dict(cls, data: dict) -> "StartupEnrichmentResponse":
        return cls(
            description=data.get("description", ""),
            website_url=data.get("website_url"),
            sector=data.get("sector", ""),
            funding=[FundingResponse.from_dict(item) for item in data.get("funding", [])],
            readiness=ReadinessResponse.from_dict(data.get("readiness", {})),
            evidence=[EvidenceResponse.from_dict(item) for item in data.get("evidence", [])],
        )
