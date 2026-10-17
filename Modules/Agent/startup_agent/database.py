"""Stores judge-approved entries in the StartupGo database, and lists the startups still to research.

An entry becomes (DB/schema.sql):

    startups               found by slug or website domain, else created; existing profile fields are only filled in when blank
    readiness_assessments  a dated snapshot: TRL/BRL from the agent's scores, CRL/IPRL/TMRL/FRL from kth.py
                           (a dimension without evidence is stored as 1, and the rationale says so)
    startup_ocean_kpis     Navigator KPI evidence from navigator.py; never lowers a level already stored
    funding_rounds         equity rounds and grants not stored yet
    sources                pages the facts came from
    agent_entries          which entry is behind the startup's agent assessment

Only entries the judge accepted are stored. Saving the same entry again changes nothing.
"""

from __future__ import annotations

import re
import sqlite3
from dataclasses import dataclass, field
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Any
from urllib.parse import urlparse

from .derive import Facts, items, value
from .errors import AgentError
from .kth import score_kth
from .navigator import ocean_kpis
from .record import StartupRecord, slugify
from .scoring import confidence_label

ASSESSOR = "StartupGo agent"
ACCEPTED = ("accepted", "accepted_with_issues")
UNKNOWN = "Unknown"
DIMENSIONS = ("crl", "trl", "brl", "iprl", "tmrl", "frl")
STAGES = {"pre_seed": "pre-seed", "seed": "seed", "series_a": "series-a", "series_b_plus": "series-b"}
ROUND_TYPES = {**STAGES, "other": "equity"}
PLACEHOLDERS = ("", UNKNOWN, "unknown")  # profile values the agent may replace
MAX_EXTRA_URLS = 3


@dataclass(frozen=True, slots=True)
class Candidate:
    """A startup to research: name + website, plus whatever else is known about it."""

    name: str
    website: str
    slug: str | None = None  # database startup it is about, if any
    business_id: str | None = None
    extra_urls: tuple[str, ...] = ()
    lead: dict[str, Any] | None = None  # discovery listing (tagline, description, sector, stage, ...)


@dataclass(slots=True)
class Stored:
    slug: str
    created: bool  # a new startup row
    assessment_id: int | None
    skipped: str = ""  # why nothing was written (not accepted, already stored)
    kpis: list[str] = field(default_factory=list)


class StartupDatabase:
    def __init__(self, path: Path):
        self.path = path

    def connect(self) -> sqlite3.Connection:
        if not self.path.exists():
            raise AgentError(f"database not found: {self.path}")
        conn = sqlite3.connect(self.path, timeout=30)
        conn.row_factory = sqlite3.Row
        conn.execute("PRAGMA foreign_keys = ON")
        if not conn.execute("SELECT 1 FROM sqlite_master WHERE type='table' AND name='agent_entries'").fetchone():
            conn.close()
            raise AgentError(f"{self.path} has no agent_entries table: start the Backend once (or run refresh.py init) to update it")
        return conn

    # --- reading -------------------------------------------------------------------------------

    def pending(self, *, limit: int, max_age_days: int, slugs: tuple[str, ...] = ()) -> list[Candidate]:
        """Startups with a website and no agent entry younger than ``max_age_days``, never researched first."""
        cutoff = (datetime.now(timezone.utc) - timedelta(days=max_age_days)).strftime("%Y-%m-%d %H:%M:%S")
        where, args = "s.website IS NOT NULL AND s.website != ''", []
        if slugs:
            where += f" AND s.slug IN ({', '.join('?' * len(slugs))})"
            args += slugs
        else:
            where += " AND (e.stored_at IS NULL OR e.stored_at < ?)"
            args.append(cutoff)
        conn = self.connect()
        try:
            rows = conn.execute(
                f"""SELECT s.id, s.slug, s.name, s.website FROM startups s LEFT JOIN agent_entries e ON e.startup_id = s.id
                    WHERE {where} ORDER BY e.stored_at IS NOT NULL, e.stored_at, s.id LIMIT ?""",
                (*args, limit),
            ).fetchall()
            return [self._candidate(conn, row) for row in rows]
        finally:
            conn.close()

    def _candidate(self, conn: sqlite3.Connection, row: sqlite3.Row) -> Candidate:
        business_id = conn.execute(
            "SELECT external_id FROM startup_external_ids WHERE startup_id = ? AND id_type = 'business_id' LIMIT 1", (row["id"],)
        ).fetchone()
        own = domain(row["website"])
        urls = [r["url"] for r in conn.execute("SELECT url FROM sources WHERE startup_id = ? ORDER BY id", (row["id"],))]
        extra = tuple(u for u in dict.fromkeys(urls) if domain(u) and domain(u) != own)[:MAX_EXTRA_URLS]
        return Candidate(row["name"], row["website"], slug=row["slug"], business_id=business_id[0] if business_id else None, extra_urls=extra)

    def known_domains(self) -> dict[str, str]:
        """Website domain -> slug of every database startup."""
        conn = self.connect()
        try:
            return {d: r["slug"] for r in conn.execute("SELECT slug, website FROM startups") if (d := domain(r["website"]))}
        finally:
            conn.close()

    # --- writing -------------------------------------------------------------------------------

    def save(self, entry: dict[str, Any], *, slug: str | None = None) -> Stored:
        """Store an evaluated, judge-reviewed entry (``StartupRecord.to_dict()``); ``slug`` pins the startup."""
        status = (entry.get("review") or {}).get("status")
        record = StartupRecord.from_dict(entry)
        conn = self.connect()
        try:
            with conn:  # one transaction: committed on return, rolled back on an error
                startup_id, slug, created = self._startup(conn, entry, record.facts, slug, write=status in ACCEPTED)
                if status not in ACCEPTED:
                    return Stored(slug or "", False, None, skipped=f"judge status {status or 'missing'}")
                known = conn.execute("SELECT entry_id, generated_at, assessment_id FROM agent_entries WHERE startup_id = ?", (startup_id,)).fetchone()
                if known and (known["entry_id"], known["generated_at"]) == (entry["id"], entry["generated_at"]):
                    return Stored(slug, False, known["assessment_id"], skipped="entry already stored")
                assessment_id = self._assessment(conn, startup_id, entry, record.facts)
                kpis = self._kpis(conn, startup_id, record.facts)
                self._rounds(conn, startup_id, record.facts)
                self._sources(conn, startup_id, entry.get("sources", []))
                self._link(conn, startup_id, entry, assessment_id)
                return Stored(slug, created, assessment_id, kpis=kpis)
        finally:
            conn.close()

    def _startup(self, conn: sqlite3.Connection, entry: dict[str, Any], facts: Facts, slug: str | None, *, write: bool) -> tuple[int, str, bool]:
        row = None
        if slug:
            row = conn.execute("SELECT * FROM startups WHERE slug = ?", (slug,)).fetchone()
            if row is None:
                raise AgentError(f"no startup with slug {slug!r} in {self.path}")
        elif own := domain(entry["website"]):
            row = next((r for r in conn.execute("SELECT * FROM startups WHERE website IS NOT NULL") if domain(r["website"]) == own), None)
        profile = _profile(entry, facts)
        if row is not None:
            blanks = {k: v for k, v in profile.items() if row[k] in (*PLACEHOLDERS, None) and v not in (*PLACEHOLDERS, None)}
            if blanks and write:
                sets = ", ".join(f"{k} = ?" for k in blanks)
                conn.execute(f"UPDATE startups SET {sets}, updated_at = datetime('now') WHERE id = ?", (*blanks.values(), row["id"]))
            return row["id"], row["slug"], False
        if not write:
            return 0, "", False
        new_slug = _unique_slug(conn, entry["name"])
        cur = conn.execute(
            f"INSERT INTO startups (slug, {', '.join(profile)}) VALUES (?, {', '.join('?' * len(profile))})",
            (new_slug, *profile.values()),
        )
        return cur.lastrowid, new_slug, True

    def _assessment(self, conn: sqlite3.Connection, startup_id: int, entry: dict[str, Any], facts: Facts) -> int:
        scores = entry["scores"]
        levels = {"trl": scores["trl"], "brl": scores["brl"], **{k: _plain(v) for k, v in score_kth(facts).items()}}
        values = {d: levels[d]["level"] or 1 for d in DIMENSIONS}
        unknown = [d.upper() for d in DIMENSIONS if levels[d]["level"] is None]
        reasons = [f"{d.upper()} {levels[d]['level']}: {levels[d]['basis'][0]}" for d in DIMENSIONS if levels[d]["level"] is not None]
        review = entry.get("review") or {}
        issues = len(review.get("open_issues", []))
        rationale = "; ".join(
            [
                *reasons,
                *([f"no evidence for {', '.join(unknown)} (stored as 1)"] if unknown else []),
                f"judge {review.get('status')}" + (f" with {issues} open issue(s)" if issues else ""),
                f"agent entry {entry['id']}",
            ]
        )
        cur = conn.execute(
            f"""INSERT INTO readiness_assessments (startup_id, assessed_on, assessor, confidence, {', '.join(DIMENSIONS)}, rationale)
                VALUES (?, ?, ?, ?, {', '.join('?' * len(DIMENSIONS))}, ?)""",
            (startup_id, entry["generated_at"][:10], ASSESSOR, confidence_label(scores["overall_confidence"]),
             *(values[d] for d in DIMENSIONS), rationale[:2000]),
        )
        return cur.lastrowid

    def _kpis(self, conn: sqlite3.Connection, startup_id: int, facts: Facts) -> list[str]:
        found = ocean_kpis(facts)
        for kpi in found:
            conn.execute(
                """INSERT INTO startup_ocean_kpis (startup_id, kpi_code, evidence_level, claim, source_url) VALUES (?, ?, ?, ?, ?)
                   ON CONFLICT (startup_id, kpi_code) DO UPDATE SET evidence_level = excluded.evidence_level,
                     claim = excluded.claim, source_url = excluded.source_url
                   WHERE excluded.evidence_level > startup_ocean_kpis.evidence_level""",
                (startup_id, kpi.code, kpi.level, kpi.claim, kpi.source_url),
            )
        return [k.code for k in found]

    def _rounds(self, conn: sqlite3.Connection, startup_id: int, facts: Facts) -> None:
        stored = {(r["round_type"], r["announced_on"]) for r in conn.execute("SELECT round_type, announced_on FROM funding_rounds WHERE startup_id = ?", (startup_id,))}
        rounds = [
            (ROUND_TYPES.get(r.value.get("stage") or "other", "equity"), r.value.get("date"), r.value.get("amount"), r.value.get("currency"),
             ", ".join(r.value.get("investors") or []) or None, r)
            for r in items(facts, "equity_rounds")
        ] + [
            ("grant", str(g.value["year"]) if g.value.get("year") else None, g.value.get("amount"), g.value.get("currency"),
             g.value.get("funder"), g)
            for g in items(facts, "grants")
        ]
        for round_type, announced_on, amount, currency, investors, fact in rounds:
            if (round_type, announced_on) in stored:
                continue
            stored.add((round_type, announced_on))
            currency = currency.upper() if isinstance(currency, str) and re.fullmatch(r"[A-Za-z]{3}", currency) else None
            conn.execute(
                """INSERT INTO funding_rounds (startup_id, round_type, amount, currency, announced_on, lead_investors, notes, source_url)
                   VALUES (?, ?, ?, ?, ?, ?, ?, ?)""",
                (startup_id, round_type, amount, currency, announced_on, investors, f"{ASSESSOR}: {fact.evidence}"[:500], fact.source_url or None),
            )

    def _sources(self, conn: sqlite3.Connection, startup_id: int, sources: list[dict[str, Any]]) -> None:
        stored = {r["url"] for r in conn.execute("SELECT url FROM sources WHERE startup_id = ?", (startup_id,))}
        for source in sources:
            if (url := source.get("url")) and url not in stored:
                stored.add(url)
                conn.execute("INSERT INTO sources (startup_id, title, url) VALUES (?, ?, ?)", (startup_id, source.get("title") or url, url))

    def _link(self, conn: sqlite3.Connection, startup_id: int, entry: dict[str, Any], assessment_id: int) -> None:
        review, scores = entry.get("review") or {}, entry["scores"]
        conn.execute(
            """INSERT INTO agent_entries (startup_id, entry_id, generated_at, stored_at, assessment_id, review_status, open_issues,
                                          investment_score, overall_confidence)
               VALUES (?, ?, ?, datetime('now'), ?, ?, ?, ?, ?)
               ON CONFLICT (startup_id) DO UPDATE SET entry_id = excluded.entry_id, generated_at = excluded.generated_at,
                 stored_at = excluded.stored_at, assessment_id = excluded.assessment_id, review_status = excluded.review_status,
                 open_issues = excluded.open_issues, investment_score = excluded.investment_score,
                 overall_confidence = excluded.overall_confidence""",
            (startup_id, entry["id"], entry["generated_at"], assessment_id, review.get("status"), len(review.get("open_issues", [])),
             scores["investment_score"], scores["overall_confidence"]),
        )


def _profile(entry: dict[str, Any], facts: Facts) -> dict[str, Any]:
    """The startups row the entry describes; unknown required fields are "Unknown"."""
    lead = entry.get("lead") or {}
    summary = value(facts, "solution_summary") or value(facts, "value_proposition") or lead.get("tagline") or ""
    parts = [value(facts, n) for n in ("solution_summary", "tech_description", "value_proposition", "ocean_problem", "impact_claim")]
    description = " ".join(dict.fromkeys(p.strip() for p in [*parts, lead.get("description")] if p and p.strip()))
    sector = value(facts, "blue_sector")
    founded = str(value(facts, "founded_date") or "")[:4]
    stage = value(facts, "stage")
    return {
        "name": entry["name"],
        "tagline": (summary or entry["name"])[:200],
        "description": description or summary or entry["name"],
        "sector": sector.replace("_", " ").capitalize() if sector and sector != "other" else lead.get("sector") or UNKNOWN,
        "country": value(facts, "country") or UNKNOWN,
        "city": value(facts, "city"),
        "founded_year": int(founded) if founded.isdigit() else None,
        "website": entry["website"],
        "stage": STAGES.get(stage, "unknown") if stage != "grant_only" else "pre-seed",
    }


def _plain(level: Any) -> dict[str, Any]:
    return {"level": level.level, "basis": level.basis}


def _unique_slug(conn: sqlite3.Connection, name: str) -> str:
    base = slug = slugify(name)
    n = 2
    while conn.execute("SELECT 1 FROM startups WHERE slug = ?", (slug,)).fetchone():
        slug, n = f"{base}-{n}", n + 1
    return slug


def domain(url: str | None) -> str:
    """Comparable website domain: lower case, without scheme, www. and port."""
    if not url:
        return ""
    host = urlparse(url if "//" in url else f"//{url}").hostname or ""
    return host.removeprefix("www.")


def entry_summary(entry: dict[str, Any], stored: Stored | None) -> dict[str, Any]:
    """What a pipeline run or a research job reports about one researched startup."""
    scores, review = entry["scores"], entry.get("review") or {}
    return {
        "entry": entry["id"],
        "name": entry["name"],
        "website": entry["website"],
        "slug": stored.slug if stored and stored.slug else None,
        "created": bool(stored and stored.created),
        "stored": bool(stored and not stored.skipped),
        "skipped": stored.skipped if stored else "no database configured",
        "trl": scores["trl"]["level"],
        "brl": scores["brl"]["level"],
        "ocean_impact_readiness": scores["ocean_impact_readiness"]["level"],
        "investment_score": scores["investment_score"],
        "overall_confidence": scores["overall_confidence"],
        "review_status": review.get("status"),
        "open_issues": len(review.get("open_issues", [])),
        "ocean_kpis": stored.kpis if stored else [],
    }

