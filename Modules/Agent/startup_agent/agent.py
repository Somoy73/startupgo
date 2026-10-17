"""The agent: discover startups through the scraper, extract facts per section, score and record them.

Pipeline for one startup (name + website):
  1. crawl the website (cached, robots.txt respected), web-search for independent pages about the
     startup, plus any extra URLs and seed documents
  2. section A first, then the PRH registry when the company looks Finnish (verified facts)
  3. one LLM call per remaining section, quotes verified in code
  4. derived facts, then scores / next steps / data gaps computed from facts
"""

from __future__ import annotations

import json
from collections.abc import Iterable, Sequence
from datetime import date, datetime
from typing import Any, Protocol

from scraper.errors import ScraperError
from scraper.models import StartupLead
from scraper.service import StartupScraper

from .crawler import PageLoader, PageSkipped, crawl_site, normalize_website
from .derive import Facts, derive_all, value
from .documents import SourceDocument, classify_source, documents_for_sections, host
from .errors import AgentError
from .extraction import SectionExtractor
from .facts import Fact, better
from .judge import ResearchFeedback
from .llm import UsageStats
from .record import StartupRecord, slugify
from .registry import PRHRegistry
from .retrievals import RetrievalLog
from .search import WebSearch
from .spec import FIELDS_BY_NAME, SECTIONS

# Search results that are login-walled, behind bot checks, or not about the company itself.
SEARCH_SKIP_DOMAINS = (
    "linkedin.com", "facebook.com", "instagram.com", "x.com", "twitter.com", "youtube.com",
    "tiktok.com", "wellfound.com", "crunchbase.com", "glassdoor.com", "google.com",
)


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
        searcher: WebSearch | None = None,
        search_queries: Sequence[str] = (),
        max_search_pages: int = 0,
        results_per_query: int = 5,
        section_groups: Sequence[Sequence[str]] | None = None,
        usage: UsageStats | None = None,
        today: str | None = None,
    ):
        self.fetcher = fetcher
        self.extractor = extractor
        self.loader = loader
        self.registry = registry
        self.max_pages = max_pages
        self.section_chars = section_chars
        self.searcher = searcher
        self.search_queries = list(search_queries)
        self.max_search_pages = max_search_pages
        self.results_per_query = results_per_query
        # Sections extracted together in one LLM call; default one call per section.
        self.section_groups = [list(g) for g in section_groups] if section_groups else [[s] for s in SECTIONS]
        self.usage = usage or UsageStats()  # LLM/search requests, cache hits, waiting, tokens
        self.today = today or date.today().isoformat()
        self.log = RetrievalLog()  # the pipeline swaps in the log its loader and searcher share (factory.py)

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
        errors: list[dict[str, str]] = []
        documents = self._collect_documents(name, website, extra_urls, seed_documents, errors)
        base: Facts = {"name": Fact("name", name, f"Input name: {name}", "", "manual", self.today, "verified", 0.9)}
        return self._build(name, website, documents, errors, base=base, business_id=business_id, lead=lead)

    def improve(self, record: StartupRecord, feedback: ResearchFeedback) -> StartupRecord:
        """Redo research as instructed by the judge: extra searches, dropped facts, re-extracted sections.

        Earlier sources are reloaded from the cache, so only new searches, new pages and the
        re-extracted sections cost anything.
        """
        errors: list[dict[str, str]] = []
        reload = [s["url"] for s in record.sources if s["source_type"] not in ("website", "registry")]
        lead = lead_from_summary(record.name, record.lead)
        seeds = [lead_document(lead, self.today)] if lead else []
        documents = self._collect_documents(record.name, record.website, reload, seeds, errors, extra_queries=feedback.queries)
        known_urls = {s["url"] for s in record.sources}
        found_new_pages = any(d.url not in known_urls for d in documents)
        wanted = feedback.sections + (feedback.search_sections if found_new_pages else [])
        sections = [s for s in SECTIONS if s in wanted]
        kept_rejections = [r for r in record.rejected if _section_of(r["field"]) not in sections]
        improved = self._build(
            record.name,
            record.website,
            documents,
            errors,
            base=_without(record.facts, feedback.drop),
            sections=sections,
            notes=feedback.notes,
            rejected=kept_rejections,
            lead=record.lead,
            registry_sources=[s for s in record.sources if s["source_type"] == "registry"],
        )
        improved.review = record.review
        return improved

    def _build(
        self,
        name: str,
        website: str,
        documents: list[SourceDocument],
        errors: list[dict[str, str]],
        *,
        base: Facts,
        sections: list[str] | None = None,
        notes: dict[str, list[str]] | None = None,
        rejected: list[dict[str, Any]] | None = None,
        business_id: str | None = None,
        lead: dict[str, Any] | None = None,
        registry_sources: list[dict[str, Any]] | None = None,
    ) -> StartupRecord:
        """Extract the requested sections (all by default) from documents and merge them into ``base``."""
        if not documents:
            raise AgentError(f"no readable documents for {name} ({website}); see crawl errors: {errors}")
        domain = host(website)
        facts: Facts = dict(base)
        rejected = list(rejected or [])
        requested = [s for s in SECTIONS if sections is None or s in sections]
        # Configured groups restricted to the requested sections; the group with A runs first (registry needs it).
        groups = [g for g in ([s for s in group if s in requested] for group in self.section_groups) if g]
        groups.sort(key=lambda g: "A" not in g)
        failed: list[str] = []

        def run_group(section_ids: list[str]) -> None:
            feedback = "\n".join(
                f"Section {sid}: {note}" if len(section_ids) > 1 else note
                for sid in section_ids
                for note in (notes or {}).get(sid, [])
            )
            try:
                result = self.extractor.extract(
                    [SECTIONS[s] for s in section_ids],
                    startup_name=name,
                    website=website,
                    documents=documents_for_sections(section_ids, documents, self.section_chars),
                    feedback=feedback,
                )
            except AgentError as exc:
                errors.extend({"stage": f"section {sid}", "url": "", "message": str(exc)} for sid in section_ids)
                failed.extend(section_ids)
                return
            for field_name, found in result.facts.items():
                facts[field_name] = merge_facts(facts.get(field_name), found)
            rejected.extend(r.to_dict() for r in result.rejected)

        registry_facts: dict[str, Fact] = {}
        for group in groups:
            run_group(group)
            if "A" in group:
                registry_facts = self._registry_facts(name, domain, business_id, facts, errors)
                for field_name, fact in registry_facts.items():
                    facts[field_name] = merge_facts(facts.get(field_name), fact)
        if sections is None and len(failed) == len(requested):
            raise AgentError(f"every section extraction failed; first error: {errors[-len(failed)]['message']}")

        for field_name, derived in derive_all(facts, website_domain=domain, today=self.today).items():
            facts[field_name] = derived  # recomputed every pass; None clears a stale value

        sources = [{"url": d.url, "title": d.title, "source_type": d.source_type, "retrieved_at": d.retrieved_at} for d in documents]
        if registry_facts:
            sources.append({"url": next(iter(registry_facts.values())).source_url, "title": "PRH Trade Register", "source_type": "registry", "retrieved_at": self.today})
        else:
            sources += registry_sources or []
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
        self,
        name: str,
        website: str,
        extra_urls: Iterable[str],
        seed_documents: Iterable[SourceDocument],
        errors: list[dict[str, str]],
        extra_queries: Iterable[str] = (),
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
        documents += self._search_documents(name, website, {d.url for d in documents}, errors, extra_queries)
        documents += list(seed_documents)
        return [d for d in documents if d.text]

    def _search_documents(
        self, name: str, website: str, seen: set[str], errors: list[dict[str, str]], extra_queries: Iterable[str] = ()
    ) -> list[SourceDocument]:
        """Independent pages about the startup found by web search (news, partners, programmes)."""
        domain = host(website)
        queries = [t.format(name=name, domain=domain) for t in self.search_queries] + list(extra_queries)
        if self.searcher is None or not queries or self.max_search_pages <= 0:
            return []
        candidates: list[str] = []
        for query in queries:
            try:
                hits = self.searcher.search(query, limit=self.results_per_query)
            except AgentError as exc:
                errors.append({"stage": "search", "url": "", "message": f"{query}: {exc}"})
                continue
            for hit in hits:
                hit_host = host(hit.url)
                skip = hit_host == domain or hit_host.endswith("." + domain) or any(
                    hit_host == d or hit_host.endswith("." + d) for d in SEARCH_SKIP_DOMAINS
                )
                if not skip and hit.url not in seen and hit.url not in candidates:
                    candidates.append(hit.url)

        documents = []
        for url in candidates:
            if len(documents) >= self.max_search_pages:
                break
            try:
                document = self.loader.load(url, source_type=classify_source(url, domain))[0]
            except (ScraperError, PageSkipped) as exc:
                errors.append({"stage": "search_result", "url": url, "message": str(exc)})
                continue
            if name.casefold() in document.text.casefold():  # only pages that are actually about the startup
                documents.append(document)
        return documents

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
    keys = ("source", "source_url", "external_id", "tagline", "description", "location", "sector", "stage")
    return {k: getattr(lead, k) for k in keys if getattr(lead, k, "")}


def lead_from_summary(name: str, summary: dict[str, Any] | None) -> StartupLead | None:
    """Rebuild a discovery lead from an entry's lead summary (to reuse its listing text as a source)."""
    if not summary or not summary.get("source_url"):
        return None
    return StartupLead(
        name=name,
        source=summary.get("source", ""),
        source_url=summary["source_url"],
        tagline=summary.get("tagline", ""),
        description=summary.get("description", ""),
    )


def merge_facts(old: Fact | list[Fact] | None, new: Fact | list[Fact] | None) -> Fact | list[Fact] | None:
    """Combine a field's facts from two passes: lists are unioned by value, single facts keep the stronger."""
    if new is None or old is None:
        return old if new is None else new
    if isinstance(new, list):
        existing = old if isinstance(old, list) else []
        seen = {_value_key(f.value) for f in existing}
        return existing + [f for f in new if _value_key(f.value) not in seen]
    return better(old if isinstance(old, Fact) else None, new)


def _without(facts: Facts, drop: Iterable[dict[str, Any]]) -> Facts:
    """Facts minus the (field, value) pairs the judge rejected."""
    out = dict(facts)
    for item in drop:
        entry = out.get(item["field"])
        if isinstance(entry, list):
            out[item["field"]] = [f for f in entry if _value_key(f.value) != _value_key(item["value"])] or None
        elif isinstance(entry, Fact) and _value_key(entry.value) == _value_key(item["value"]):
            out[item["field"]] = None
    return {k: v for k, v in out.items() if v is not None}


def _value_key(value: Any) -> str:
    return json.dumps(value, sort_keys=True, ensure_ascii=False)


def _section_of(field_name: str) -> str | None:
    spec = FIELDS_BY_NAME.get(field_name)
    return spec.section if spec else None
