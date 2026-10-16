"""Agent-facing tools that compose discovery, documents, and enrichment."""

from __future__ import annotations

from .ai.enricher import StartupEnricher
from .documents import PublicDocumentService
from .models import StartupLead, StartupProfile
from .service import StartupScraper


class StartupResearchTools:
    """Small tool surface suitable for an agent framework."""

    def __init__(
        self,
        scraper: StartupScraper,
        documents: PublicDocumentService,
        enricher: StartupEnricher,
    ):
        self.scraper = scraper
        self.documents = documents
        self.enricher = enricher

    def search_startups(
        self,
        *,
        source: str,
        url: str | None = None,
        query: str | None = None,
        location: str = "",
        limit: int = 50,
    ) -> list[StartupLead]:
        return self.scraper.collect(
            source=source,
            url=url,
            query=query,
            location=location,
            limit=limit,
        )

    def enrich_startup(self, lead: StartupLead) -> StartupProfile:
        urls = list(dict.fromkeys(filter(None, (lead.source_url, lead.website))))
        documents = [
            self.documents.load(url=url, source=lead.source)
            for url in urls
        ]
        return self.enricher.enrich(lead=lead, documents=documents)
