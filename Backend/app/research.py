"""Research jobs: the agent researches a startup in the background and stores what the judge accepts.

    POST /api/research  → a queued job (agent_jobs row) → one worker thread runs ResearchPipeline.research
                        → the startup's new assessment is in the database (Modules/Agent/startup_agent/database.py)

Only startups without a usable score get a job: none yet, or one where the agent found no evidence for
TRL or BRL (main.py answers 409 for any other assessment). A startup the agent researched in the last
[pipeline] max_age_days (30) isn't researched again, whatever the result (startups.agent_researched_at). Those are researched again with refresh, ignoring
the agent's cache of pages and LLM outputs, which would otherwise give the same empty answer.
Jobs run one at a time: the agent's LLM calls share one rate limit. A job for a startup that already
has one queued or running returns that job. Jobs still open when the Backend stops are marked as
errors on the next start. Search sees the new data after `process-storage` runs.
"""

import json
import sqlite3
from collections.abc import Callable
from concurrent.futures import ThreadPoolExecutor
from dataclasses import replace
from typing import Any

from startup_agent import Candidate
from startup_agent.database import missing_levels, researched_within

from .db import connect, db_path
from .schemas import ResearchJob

Research = Callable[[Candidate, bool], dict[str, Any]]  # (candidate, refresh) -> summary
REQUIRED_LEVELS = ("trl", "brl")  # a score without evidence for one of these is researched again

JOB_SQL = """
SELECT j.*, s.slug FROM agent_jobs j LEFT JOIN startups s ON s.id = j.startup_id
WHERE j.id = ?
"""


def researched_recently(conn: sqlite3.Connection, startup_id: int) -> tuple[str, int] | None:
    """When the agent last researched the startup, and the agent's max_age_days, if it is too soon to research it again."""
    from startup_agent import AgentSettings

    days = AgentSettings.load().pipeline.max_age_days
    ran = researched_within(conn, startup_id, days)
    return (ran, days) if ran else None


def needs_research(conn: sqlite3.Connection, startup_id: int) -> bool:
    """Whether the startup's latest assessment has no evidence for TRL or BRL (the agent stored them as 1)."""
    return any(level in REQUIRED_LEVELS for level in missing_levels(conn, startup_id))


def research_with_agent(candidate: Candidate, refresh: bool) -> dict[str, Any]:
    """The agent's research workflow on this Backend's database (settings from Modules/Agent/config.toml)."""
    from startup_agent import AgentSettings, ResearchPipeline

    pipeline = ResearchPipeline(replace(AgentSettings.load(), database=db_path()), refresh=refresh)
    try:
        return pipeline.research(candidate)
    finally:
        pipeline.close()


class ResearchJobs:
    def __init__(self, research: Research = research_with_agent):
        self.research = research
        self._executor = ThreadPoolExecutor(max_workers=1, thread_name_prefix="research")

    def recover(self, conn: sqlite3.Connection) -> None:
        """Jobs left open by a previous run will never finish."""
        with conn:
            conn.execute(
                "UPDATE agent_jobs SET status = 'error', error = 'interrupted: the Backend restarted', finished_at = datetime('now') "
                "WHERE status IN ('queued', 'running')"
            )

    def submit(self, conn: sqlite3.Connection, candidate: Candidate, startup_id: int | None, *, refresh: bool = False) -> ResearchJob:
        open_job = conn.execute(
            "SELECT id FROM agent_jobs WHERE status IN ('queued', 'running') AND (startup_id = ? OR website = ?) ORDER BY id LIMIT 1",
            (startup_id, candidate.website),
        ).fetchone()
        if open_job:
            return get_job(conn, open_job["id"])
        request = {"business_id": candidate.business_id, "urls": list(candidate.extra_urls), "refresh": refresh}
        with conn:
            job_id = conn.execute(
                "INSERT INTO agent_jobs (startup_id, name, website, request, status) VALUES (?, ?, ?, ?, 'queued')",
                (startup_id, candidate.name, candidate.website, json.dumps(request)),
            ).lastrowid
        self._executor.submit(self._run, job_id, candidate, refresh)
        return get_job(conn, job_id)

    def _run(self, job_id: int, candidate: Candidate, refresh: bool) -> None:
        conn = connect()
        try:
            with conn:
                conn.execute("UPDATE agent_jobs SET status = 'running', started_at = datetime('now') WHERE id = ?", (job_id,))
            try:
                result = self.research(candidate, refresh)
            except Exception as exc:  # the agent's errors, and anything unexpected: the job records it
                with conn:
                    conn.execute(
                        "UPDATE agent_jobs SET status = 'error', error = ?, finished_at = datetime('now') WHERE id = ?",
                        (str(exc) or type(exc).__name__, job_id),
                    )
                return
            startup = conn.execute("SELECT id FROM startups WHERE slug = ?", (result.get("slug"),)).fetchone() if result.get("slug") else None
            with conn:
                conn.execute(
                    """UPDATE agent_jobs SET status = 'done', result = ?, finished_at = datetime('now'),
                       startup_id = COALESCE(?, startup_id) WHERE id = ?""",
                    (json.dumps(result, ensure_ascii=False), startup["id"] if startup else None, job_id),
                )
        finally:
            conn.close()

    def shutdown(self) -> None:
        self._executor.shutdown(wait=False, cancel_futures=True)


def get_job(conn: sqlite3.Connection, job_id: int) -> ResearchJob | None:
    row = conn.execute(JOB_SQL, (job_id,)).fetchone()
    return _job(row) if row else None


def latest_job(conn: sqlite3.Connection, startup_id: int) -> ResearchJob | None:
    row = conn.execute(
        "SELECT j.*, s.slug FROM agent_jobs j LEFT JOIN startups s ON s.id = j.startup_id WHERE j.startup_id = ? ORDER BY j.id DESC LIMIT 1",
        (startup_id,),
    ).fetchone()
    return _job(row) if row else None


def _job(row: sqlite3.Row) -> ResearchJob:
    request = json.loads(row["request"])
    return ResearchJob(
        id=row["id"],
        status=row["status"],
        name=row["name"],
        website=row["website"],
        slug=row["slug"],
        business_id=request.get("business_id"),
        urls=request.get("urls", []),
        refresh=request.get("refresh", False),
        created_at=row["created_at"],
        started_at=row["started_at"],
        finished_at=row["finished_at"],
        result=json.loads(row["result"]) if row["result"] else None,
        error=row["error"],
    )
