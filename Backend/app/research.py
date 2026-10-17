"""Research jobs: the agent researches a startup in the background and stores its scores.

    POST /api/research  → a queued job → one worker thread runs ResearchPipeline.research
                        → the run's assessment is in the assessments table (Modules/Agent/startup_agent/database.py)

Only startups without a usable score get a job: none yet, or the agent's latest without evidence for TRL or BRL
(main.py answers 409 for any other score). A startup the agent researched in the last [pipeline] max_age_days (30)
isn't researched again, whatever the judge decided (the agent's assessments rows). Those are researched again with
refresh, ignoring the agent's cache of pages and LLM outputs, which would otherwise give the same empty answer.
Jobs run one at a time: the agent's LLM calls share one rate limit. A job for a startup that already has one queued
or running returns that job. Jobs live in memory: the results are in the database, the job list starts empty on
each start. Search sees the new data after `process-storage` runs.
"""

import sqlite3
import threading
from collections.abc import Callable
from concurrent.futures import ThreadPoolExecutor
from dataclasses import dataclass, replace
from datetime import datetime, timezone
from typing import Any

from startup_agent import Candidate
from startup_agent.database import REQUIRED_LEVELS, missing_levels, researched_within

from .db import connect, db_path
from .schemas import ResearchJob

Research = Callable[[Candidate, bool], dict[str, Any]]  # (candidate, refresh) -> summary


def researched_recently(conn: sqlite3.Connection, startup_id: int) -> tuple[str, int] | None:
    """When the agent last researched the startup, and the agent's max_age_days, if it is too soon to research it again."""
    from startup_agent import AgentSettings

    days = AgentSettings.load().pipeline.max_age_days
    ran = researched_within(conn, startup_id, days)
    return (ran, days) if ran else None


def needs_research(conn: sqlite3.Connection, startup_id: int) -> bool:
    """Whether the startup's latest score has no evidence for TRL or BRL (the agent stored them as 1)."""
    return any(level in REQUIRED_LEVELS for level in missing_levels(conn, startup_id))


def research_with_agent(candidate: Candidate, refresh: bool) -> dict[str, Any]:
    """The agent's research workflow on this Backend's database (settings from Modules/Agent/config.toml)."""
    from startup_agent import AgentSettings, ResearchPipeline

    pipeline = ResearchPipeline(replace(AgentSettings.load(), database=db_path()), refresh=refresh)
    try:
        return pipeline.research(candidate)
    finally:
        pipeline.close()


def _now() -> str:
    return datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M:%S")


@dataclass(slots=True)
class _Job:
    job: ResearchJob
    startup_id: int | None


class ResearchJobs:
    def __init__(self, research: Research = research_with_agent):
        self.research = research
        self._executor = ThreadPoolExecutor(max_workers=1, thread_name_prefix="research")
        self._jobs: dict[int, _Job] = {}
        self._lock = threading.Lock()

    def submit(self, candidate: Candidate, startup_id: int | None, *, refresh: bool = False) -> ResearchJob:
        with self._lock:
            open_job = next((j.job for j in self._jobs.values() if j.job.status in ("queued", "running")
                             and ((startup_id is not None and j.startup_id == startup_id) or j.job.website == candidate.website)), None)
            if open_job:
                return open_job
            job = ResearchJob(id=len(self._jobs) + 1, status="queued", name=candidate.name, website=candidate.website, slug=candidate.slug,
                              business_id=candidate.business_id, urls=list(candidate.extra_urls), refresh=refresh, created_at=_now(),
                              started_at=None, finished_at=None, result=None, error=None)
            self._jobs[job.id] = _Job(job, startup_id)
        self._executor.submit(self._run, job.id, candidate, refresh)
        return job

    def _update(self, job_id: int, startup_id: int | None = None, **changes: Any) -> None:
        with self._lock:
            entry = self._jobs[job_id]
            entry.job = entry.job.model_copy(update=changes)
            entry.startup_id = startup_id or entry.startup_id

    def _run(self, job_id: int, candidate: Candidate, refresh: bool) -> None:
        self._update(job_id, status="running", started_at=_now())
        try:
            result = self.research(candidate, refresh)
        except Exception as exc:  # the agent's errors, and anything unexpected: the job records it
            self._update(job_id, status="error", error=str(exc) or type(exc).__name__, finished_at=_now())
            return
        slug, startup_id = result.get("slug"), None
        if slug:
            conn = connect()
            try:
                row = conn.execute("SELECT id FROM entities WHERE kind = 'startup' AND slug = ?", (slug,)).fetchone()
            finally:
                conn.close()
            startup_id = row["id"] if row else None
        changes = {"slug": slug} if startup_id else {}
        self._update(job_id, startup_id, status="done", result=result, finished_at=_now(), **changes)

    def get(self, job_id: int) -> ResearchJob | None:
        with self._lock:
            entry = self._jobs.get(job_id)
            return entry.job if entry else None

    def latest(self, startup_id: int) -> ResearchJob | None:
        """The startup's latest job since the Backend started."""
        with self._lock:
            return next((j.job for j in reversed(self._jobs.values()) if j.startup_id == startup_id), None)

    def shutdown(self) -> None:
        self._executor.shutdown(wait=False, cancel_futures=True)
