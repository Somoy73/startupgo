"""The research pipeline: candidates (name + website + info) → agent → judge → entry file + database.

    candidates  database startups without a usable score (database.py), then leads from the [pipeline]
                discover sources (Wellfound, directories, OSM) that aren't in the database yet
    research    per candidate, the LangGraph workflow (graph.py): research → judge → evaluation → judge
    store       the evaluated entry → output/startups/<id>.json, its scores → the assessments table (database.py)

Search sees the new data after `process-storage` runs (refresh.py's agent and search_index steps
run both). The Backend's research jobs call ``research`` for one candidate.
"""

from __future__ import annotations

from collections.abc import Callable, Iterable
from typing import Any

from scraper.fetchers import PublicPageFetcher

from .agent import StartupAgent, _lead_summary
from .config import AgentSettings
from .database import Candidate, StartupDatabase, domain, entry_summary
from .errors import AgentError
from .factory import build_agent, build_judge
from .graph import build_agent_graph
from .record import StartupRecord
from .store import RecordStore

AgentBuilder = Callable[..., tuple[StartupAgent, PublicPageFetcher]]


class ResearchPipeline:
    def __init__(self, settings: AgentSettings, *, refresh: bool = False, build: AgentBuilder = build_agent):
        self.settings = settings
        self.store = RecordStore(settings.output_dir)
        self.database = StartupDatabase(settings.database) if settings.database else None
        self._build = build
        self._refresh = refresh
        self._agent: StartupAgent | None = None
        self._fetcher: PublicPageFetcher | None = None
        self._workflow: Any = None

    @property
    def agent(self) -> StartupAgent:
        if self._agent is None:
            self._agent, self._fetcher = self._build(self.settings, refresh=self._refresh)
        return self._agent

    def candidates(
        self,
        *,
        limit: int | None = None,
        slugs: Iterable[str] = (),
        discover: bool = True,
        sources: Iterable[dict[str, Any]] | None = None,
    ) -> tuple[list[Candidate], list[str]]:
        """Up to ``limit`` startups to research (pending database startups first), and discovery problems.

        ``sources`` replaces the [pipeline] discover sources, and then only discovered startups are candidates.
        """
        limit = limit or self.settings.pipeline.limit
        slugs = tuple(slugs)
        only_discovered = sources is not None
        sources = list(self.settings.pipeline.discover if sources is None else sources)
        found = [] if only_discovered or not self.database else self.database.pending(
            limit=limit, max_age_days=self.settings.pipeline.max_age_days, slugs=slugs)
        problems: list[str] = []
        if not discover or slugs or len(found) >= limit:
            return found[:limit], problems
        seen = set(self.database.known_domains() if self.database else {}) | {domain(c.website) for c in found}
        for source in sources:
            if len(found) >= limit:
                break
            try:
                leads = self.agent.discover(**source)
            except AgentError as exc:
                problems.append(f"discovery {source['source']} {source['url'] or source['query']}: {exc}")
                continue
            for lead in leads:
                if (d := domain(lead.website)) and d not in seen:
                    seen.add(d)
                    found.append(Candidate(lead.name, lead.website, lead=_lead_summary(lead)))
        return found[:limit], problems

    def research(self, candidate: Candidate) -> dict[str, Any]:
        """Research, judge and store one startup; returns its summary (database.entry_summary) and run errors."""
        if self._workflow is None:
            self._workflow = build_agent_graph(self.agent, judge=build_judge(self.settings, self.agent), weights=self.settings.weights)
        result = self._workflow.invoke({
            "mode": "both",
            "name": candidate.name,
            "website": candidate.website,
            "business_id": candidate.business_id,
            "extra_urls": list(candidate.extra_urls),
            "lead": candidate.lead,
            "records": [],
        })
        problems = [*result.get("errors", []), *(f"{s['name']}: {s['reason']}" for s in result.get("skipped", []))]
        if not result.get("evaluated"):
            raise AgentError("; ".join(problems) or "research produced no entry")
        _, entry = self.store.save(StartupRecord.from_dict(result["evaluated"][0]), weights=self.settings.weights)
        stored = self.database.save(entry, slug=candidate.slug) if self.database else None
        return {**entry_summary(entry, stored), "errors": problems}

    def run(self, candidates: Iterable[Candidate]) -> list[dict[str, Any]]:
        """Research every candidate; a failure is reported in its result and the run continues."""
        results = []
        for candidate in candidates:
            try:
                results.append(self.research(candidate))
            except AgentError as exc:
                results.append({"name": candidate.name, "website": candidate.website, "slug": candidate.slug, "stored": False, "error": str(exc)})
        return results

    def usage(self) -> str:
        return self._agent.usage.summary() if self._agent else "no LLM calls"

    def close(self) -> None:
        if self._fetcher is not None:
            self._fetcher.close()
