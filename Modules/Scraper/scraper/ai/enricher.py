"""AI-powered startup profile enrichment."""

from __future__ import annotations

from ..documents import SourceDocument
from ..models import Evidence, FundingEvidence, ReadinessEvidence, StartupLead, StartupProfile
from .provider import AIProvider
from .schemas import EvidenceResponse, StartupEnrichmentResponse


class StartupEnricher:
    def __init__(self, provider: AIProvider):
        self.provider = provider

    def enrich(self, *, lead: StartupLead, documents: list[SourceDocument]) -> StartupProfile:
        source_text = "\n\n".join(
            f"Source URL: {document.url}\nTitle: {document.title}\n{document.text}"
            for document in documents
        )
        response = self.provider.generate_structured(
            system_prompt=self._system_prompt(),
            user_prompt=f"Startup name: {lead.name}\nKnown source URL: {lead.source_url}\n{source_text}",
            response_type=StartupEnrichmentResponse,
        )
        return self._to_profile(lead, response)

    @staticmethod
    def _system_prompt() -> str:
        return (
            "You are a startup research analyst. Extract only facts supported by the "
            "public documents. Never fabricate funding, TRL, BRL, dates, or investors. "
            "Use null for missing values. Every important fact needs a source URL and "
            "short quote. TRL and BRL are integers from 1 to 9. Mark inferred values "
            "as origin='inferred' and use low or medium confidence."
        )

    def _to_profile(self, lead: StartupLead, response: StartupEnrichmentResponse) -> StartupProfile:
        return StartupProfile(
            lead=lead,
            description=response.description,
            website_url=response.website_url or lead.website,
            sector=response.sector or lead.sector,
            funding=[
                FundingEvidence(
                    round_type=item.round_type,
                    amount=item.amount,
                    currency=item.currency,
                    announced_on=item.announced_on,
                    investors=item.investors,
                    evidence=[self._evidence(evidence) for evidence in item.evidence],
                )
                for item in response.funding
            ],
            readiness=ReadinessEvidence(
                trl=response.readiness.trl,
                brl=response.readiness.brl,
                trl_evidence=[self._evidence(item) for item in response.readiness.trl_evidence],
                brl_evidence=[self._evidence(item) for item in response.readiness.brl_evidence],
            ),
            evidence=[self._evidence(item) for item in response.evidence],
        )

    @staticmethod
    def _evidence(item: EvidenceResponse) -> Evidence:
        if item.confidence not in {"low", "medium", "high"}:
            raise ValueError(f"invalid evidence confidence: {item.confidence}")
        if item.origin not in {"explicit", "inferred", "unknown"}:
            raise ValueError(f"invalid evidence origin: {item.origin}")
        return Evidence(
            value=item.value,
            source_url=item.source_url,
            quote=item.quote,
            confidence=item.confidence,
            origin=item.origin,
        )
