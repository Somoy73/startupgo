"""Research jobs: the agent researches a startup in the background and stores what the judge accepts.

    POST /api/research  → a queued job (agent_jobs row) → one worker thread runs ResearchPipeline.research
                        → the startup's new assessment is in the database (Modules/Agent/startup_agent/database.py)

Only startups without a score get a job (main.py answers 409 for one that has an assessment).
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

from .db import connect, db_path
from .schemas import ResearchJob

Research = Callable[[Candidate], dict[str, Any]]

JOB_SQL = """
SELECT j.*, s.slug FROM agent_jobs j LEFT JOIN startups s ON s.id = j.startup_id
WHERE j.id = ?
"""


def research_with_agent(candidate: Candidate) -> dict[str, Any]:
    """The agent's research workflow on this Backend's database (settings from Modules/Agent/config.toml)."""
    from startup_agent import AgentSettings, ResearchPipeline

    pipeline = ResearchPipeline(replace(AgentSettings.load(), database=db_path()))
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

    def submit(self, conn: sqlite3.Connection, candidate: Candidate, startup_id: int | None) -> ResearchJob:
        open_job = conn.execute(
            "SELECT id FROM agent_jobs WHERE status IN ('queued', 'running') AND (startup_id = ? OR website = ?) ORDER BY id LIMIT 1",
            (startup_id, candidate.website),
        ).fetchone()
        if open_job:
            return get_job(conn, open_job["id"])
        request = {"business_id": candidate.business_id, "urls": list(candidate.extra_urls)}
        with conn:
            job_id = conn.execute(
                "INSERT INTO agent_jobs (startup_id, name, website, request, status) VALUES (?, ?, ?, ?, 'queued')",
                (startup_id, candidate.name, candidate.website, json.dumps(request)),
            ).lastrowid
        self._executor.submit(self._run, job_id, candidate)
        return get_job(conn, job_id)

    def _run(self, job_id: int, candidate: Candidate) -> None:
        conn = connect()
        try:
            with conn:
                conn.execute("UPDATE agent_jobs SET status = 'running', started_at = datetime('now') WHERE id = ?", (job_id,))
            try:
                result = self.research(candidate)
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
        created_at=row["created_at"],
        started_at=row["started_at"],
        finished_at=row["finished_at"],
        result=json.loads(row["result"]) if row["result"] else None,
        error=row["error"],
    )
