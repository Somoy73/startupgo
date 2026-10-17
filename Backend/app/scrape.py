"""Scrape jobs: the scrape agent reads pages, PDFs and images for one or several sources in the background.

    POST /api/agent-scrape  → a queued job → one worker thread runs ScrapeAgent.run (Modules/Agent/startup_agent/scrape.py)
    GET  /api/agent-scrape/{id}             → its progress while it runs, then the merged records, gaps and sources
    POST /api/agent-scrape/startups         → a scraped startup into the database (StartupDatabase.add_scraped)

Jobs run one at a time (one stealth Chrome, one LLM rate limit) and live in memory: the list starts empty on each start.
"""

import os
import threading
from collections.abc import Callable
from concurrent.futures import ThreadPoolExecutor
from datetime import datetime, timezone
from typing import Any

from startup_agent import AgentSettings, ScrapeAgent, ScrapeTask, StartupDatabase

from .db import db_path
from .schemas import ScrapeAgentInfo, ScrapedStartup, ScrapedStartupAdded, ScrapeJob, ScrapeModel, ScrapeRequest

Scrape = Callable[[list[ScrapeTask], Callable[[str], None], ScrapeRequest], dict[str, Any]]  # (tasks, progress, request) -> result


def scrape_with_agent(tasks: list[ScrapeTask], progress: Callable[[str], None], request: ScrapeRequest) -> dict[str, Any]:
    """The scrape agent with the settings from Modules/Agent/config.toml."""
    return ScrapeAgent().run(tasks, progress, stealth=request.stealth, llm=request.llm)


def add_startup(body: ScrapedStartup) -> ScrapedStartupAdded:
    """A scraped startup as a sourced startup of this Backend's database (raises AgentError without name and website)."""
    return ScrapedStartupAdded(**StartupDatabase(db_path()).add_scraped(body.record.model_dump(), website=body.website))


def agent_info() -> ScrapeAgentInfo:
    settings = AgentSettings.load()
    models = [ScrapeModel(name=m.name, provider=m.provider, model=m.model, multimodal=m.reads_images, key_set=bool(os.getenv(m.api_key_env, "").strip()))
              for m in settings.llms.values()]
    return ScrapeAgentInfo(default=settings.llm.name, models=models, web_search=settings.search.provider != "none")


def _now() -> str:
    return datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M:%S")


class ScrapeJobs:
    def __init__(self, scrape: Scrape = scrape_with_agent):
        self.scrape = scrape
        self._executor = ThreadPoolExecutor(max_workers=1, thread_name_prefix="scrape")
        self._jobs: dict[int, ScrapeJob] = {}
        self._lock = threading.Lock()

    def submit(self, request: ScrapeRequest) -> ScrapeJob:
        with self._lock:
            job = ScrapeJob(id=len(self._jobs) + 1, status="queued", sources=request.sources, stealth=request.stealth, llm=request.llm,
                            created_at=_now(), started_at=None, finished_at=None, progress=[], result=None, error=None)
            self._jobs[job.id] = job
        tasks = [ScrapeTask(s.goal, tuple(s.urls), follow_links=s.follow_links, max_pages=s.max_pages, mode=s.mode, label=s.label)
                 for s in request.sources]
        self._executor.submit(self._run, job.id, tasks, request)
        return job

    def _update(self, job_id: int, **changes: Any) -> None:
        with self._lock:
            self._jobs[job_id] = self._jobs[job_id].model_copy(update=changes)

    def _progress(self, job_id: int, message: str) -> None:
        with self._lock:
            job = self._jobs[job_id]
            self._jobs[job_id] = job.model_copy(update={"progress": [*job.progress, message]})

    def _run(self, job_id: int, tasks: list[ScrapeTask], request: ScrapeRequest) -> None:
        self._update(job_id, status="running", started_at=_now())
        try:
            result = self.scrape(tasks, lambda message: self._progress(job_id, message), request)
        except Exception as exc:  # the agent's errors, and anything unexpected: the job records it
            self._update(job_id, status="error", error=str(exc) or type(exc).__name__, finished_at=_now())
            return
        self._update(job_id, status="done", result=result, finished_at=_now())

    def get(self, job_id: int) -> ScrapeJob | None:
        with self._lock:
            return self._jobs.get(job_id)

    def shutdown(self) -> None:
        self._executor.shutdown(wait=False, cancel_futures=True)
