"""The agent: discover startups through the scraper, extract facts per section, score and record them.

Pipeline for one startup (name + website):
  1. crawl the website (cached, robots.txt respected) plus any extra URLs and seed documents
  2. section A first, then the PRH registry when the company looks Finnish (verified facts)
  3. one LLM call per remaining section, quotes verified in code
  4. derived facts, then scores / next steps / data gaps computed from facts
"""

from __future__ import annotations

from collections.abc import Iterable
from datetime import date, datetime
from typing import Any, Protocol

from scraper.errors import ScraperError
from scraper.models import StartupLead
from scraper.service import StartupScraper

from .crawler import PageLoader, PageSkipped, crawl_site, normalize_website
from .derive import Facts, derive_all, value
from .documents import SourceDocument, classify_source, documents_for_section, host
from .errors import AgentError
from .extraction import SectionExtractor
from .facts import Fact, better
from .record import StartupRecord, slugify
from .registry import PRHRegistry
from .spec import SECTIONS


class Fetcher(Protocol):
    user_agent: str

    def fetch_text(self, url: str) -> str: ...
    def fetch_json(self, url: str) -> Any: ...


class StartupAgent:
    def __init__(
        self,
        *,
        fetcher: Fetcher,
        extractor: SectionExtractor,
        loader: PageLoader,
        registry: PRHRegistry,
        max_pages: int,
        section_chars: int,
        today: str | None = None,
    ):
        self.fetcher = fetcher
        self.extractor = extractor
        self.loader = loader
        self.registry = registry
        self.max_pages = max_pages
        self.section_chars = section_chars
        self.today = today or date.today().isoformat()

    # --- discovery ------------------------------------------------------------------

    def discover(self, *, source: str, url: str | None = None, query: str | None = None, location: str = "", limit: int = 10) -> list[StartupLead]:
        try:
            return StartupScraper(self.fetcher).collect(source=source, url=url, query=query, location=location, limit=limit)
        except ScraperError as exc:
            raise AgentError(f"discovery failed: {exc}") from exc

    def profile_lead(self, lead: StartupLead) -> StartupRecord:
        if not lead.website:
            raise AgentError(f"{lead.name}: the lead has no website to profile")
        return self.profile(name=lead.name, website=lead.website, seed_documents=[lead_document(lead, self.today)], lead=_lead_summary(lead))

    # --- profiling --------------------------------------------------------------------

    def profile(
        self,
        *,
        name: str,
        website: str,
        business_id: str | None = None,
        extra_urls: Iterable[str] = (),
        seed_documents: Iterable[SourceDocument] = (),
        lead: dict[str, Any] | None = None,
    ) -> StartupRecord:
        website = normalize_website(website)
        domain = host(website)
        errors: list[dict[str, str]] = []
        documents = self._collect_documents(website, extra_urls, seed_documents, errors)
        if not documents:
            raise AgentError(f"no readable documents for {name} ({website}); see crawl errors: {errors}")

        facts: Facts = {"name": Fact("name", name, f"Input name: {name}", "", "manual", self.today, "verified", 0.9)}
        rejected: list[dict[str, Any]] = []
        failed_sections: list[str] = []

        def run_section(section_id: str) -> None:
            section = SECTIONS[section_id]
            try:
                result = self.extractor.extract(
                    section,
                    startup_name=name,
                    website=website,
                    documents=documents_for_section(section_id, documents, self.section_chars),
                )
            except AgentError as exc:
                errors.append({"stage": f"section {section_id}", "url": "", "message": str(exc)})
                failed_sections.append(section_id)
                return
            facts.update(result.facts)
            rejected.extend(r.to_dict() for r in result.rejected)

        run_section("A")
        registry_facts = self._registry_facts(name, domain, business_id, facts, errors)
        for field, fact in registry_facts.items():
            existing = facts.get(field)
            facts[field] = better(existing if isinstance(existing, Fact) else None, fact)
        for section_id in SECTIONS:
            if section_id != "A":
                run_section(section_id)
        if len(failed_sections) == len(SECTIONS):
            raise AgentError(f"every section extraction failed; first error: {errors[-len(SECTIONS)]['message']}")
        facts.update({k: v for k, v in derive_all(facts, website_domain=domain, today=self.today).items() if v is not None})

        sources = [{"url": d.url, "title": d.title, "source_type": d.source_type, "retrieved_at": d.retrieved_at} for d in documents]
        if registry_facts:
            sources.append({"url": next(iter(registry_facts.values())).source_url, "title": "PRH Trade Register", "source_type": "registry", "retrieved_at": self.today})
        return StartupRecord(
            id=slugify(domain),
            name=name,
            website=website,
            generated_at=datetime.now().astimezone().replace(microsecond=0).isoformat(),
            facts={k: v for k, v in facts.items() if v is not None},
            sources=sources,
            rejected=rejected,
            errors=errors,
            lead=lead,
        )

    def _collect_documents(
        self, website: str, extra_urls: Iterable[str], seed_documents: Iterable[SourceDocument], errors: list[dict[str, str]]
    ) -> list[SourceDocument]:
        documents: list[SourceDocument] = []
        try:
            documents += crawl_site(self.loader, website, max_pages=self.max_pages, errors=errors)
        except (ScraperError, PageSkipped) as exc:
            errors.append({"stage": "crawl", "url": website, "message": str(exc)})
        domain = host(website)
        for url in extra_urls:
            try:
                documents.append(self.loader.load(url, source_type=classify_source(url, domain))[0])
            except (ScraperError, PageSkipped) as exc:
                errors.append({"stage": "extra_url", "url": url, "message": str(exc)})
        documents += list(seed_documents)
        return [d for d in documents if d.text]

    def _registry_facts(
        self, name: str, domain: str, business_id: str | None, facts: Facts, errors: list[dict[str, str]]
    ) -> dict[str, Fact]:
        """PRH facts when we have a business ID or the company looks Finnish."""
        business_id = business_id or value(facts, "business_id")
        finnish = domain.endswith(".fi") or value(facts, "country") == "Finland"
        if not (business_id or finnish):
            return {}
        try:
            return self.registry.lookup(name=name, business_id=business_id, website_domain=domain, allow_name_match=finnish)
        except ScraperError as exc:
            errors.append({"stage": "registry", "url": "", "message": str(exc)})
            return {}


def lead_document(lead: StartupLead, today: str) -> SourceDocument:
    """Discovery listing text as a source. It is company-submitted, so it counts as the startup's own claim."""
    text = "\n".join(part for part in (lead.name, lead.tagline, lead.description) if part)
    return SourceDocument(lead.source_url, f"{lead.source} listing: {lead.name}", text, "website", today)


def _lead_summary(lead: StartupLead) -> dict[str, Any]:
    keys = ("source", "source_url", "external_id", "tagline", "location", "sector", "stage")
    return {k: getattr(lead, k) for k in keys if getattr(lead, k, "")}
