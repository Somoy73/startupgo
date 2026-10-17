"""Reads and writes startup scores in the StartupGo database: entities, facts, assessments (DB/unified.sql).

Which startups to research comes from the assessments table: startups with a website and no usable score (no
assessment with all six KTH levels, or the agent's latest one without evidence for TRL or BRL), that the agent
hasn't researched in the last max_age_days, never researched first.

An evaluated, judge-reviewed entry becomes:

    entities     the startup, found by slug or website domain (a BlueInvest candidate becomes a startup), else created;
                 existing profile fields are only filled in when blank
    assessments  one row per agent run: engine 'agent', assessed_at = the entry's generated_at (UTC)
                 - judge accepted: the scores. TRL, BRL, OIR and the 10 criteria from scoring.py, CRL/IPRL/TMRL/FRL from
                   kth.py; a dimension without evidence is stored as 1 and levels_basis gives its level as null
                 - judged but not accepted: only the run (judge status, levels_basis, criteria), no score columns, so
                   it never becomes the startup's score but still counts as researched
    facts        accepted entries only, source_name 'agent': the entry's facts (replacing the agent's earlier ones),
                 Navigator KPI evidence from navigator.py (never lowers a level already stored), and the pages the
                 facts came from (reference). A round already stored from another source is kept, not current

A new startup whose entry the judge didn't accept isn't stored. Saving the same entry again changes nothing.

add_scraped stores a startup the scrape agent found (scrape.py) when a user asks for it: a sourced startup without a
score, found by website domain first (a BlueInvest candidate becomes a startup, a known startup only gets the evidence),
plus the record as one facts row (source_name 'scraper', section 'Api'). Opening the startup then queues the research
agent, which scores it.

scores_of gives any startup's Investment Score Matrix by the agent's rubric (scoring.py), for the Backend: the agent's
latest accepted assessment, else the rubric applied to the startup's facts (facts_of), read the way the agent reads them.
"""

from __future__ import annotations

import json
import re
import sqlite3
from dataclasses import asdict, dataclass, field
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Any
from urllib.parse import urlparse

from .agent import merge_facts
from .derive import Facts, derive_all, value
from .errors import AgentError
from .facts import INFERRED_CONFIDENCE, Fact, InvalidValue, coerce
from .kth import score_kth
from .navigator import ocean_kpis
from .record import StartupRecord, slugify
from .retrievals import Retrieval
from .scoring import confidence_label, investment_percent, score_all
from .spec import FIELDS_BY_NAME

ENGINE = "agent"  # assessments.engine and facts.source_name of everything the agent writes
SCRAPER = "scraper"  # facts.source_name of the records the scrape agent stores
ASSESSOR = "StartupGo agent"
ACCEPTED = ("accepted", "accepted_with_issues")
UNKNOWN = "Unknown"
DIMENSIONS = ("crl", "trl", "brl", "iprl", "tmrl", "frl")
REQUIRED_LEVELS = ("trl", "brl")  # a score without evidence for one of these is researched again
HAS_LEVELS = " AND ".join(f"{d} IS NOT NULL" for d in DIMENSIONS)
STAGES = {"pre_seed": "pre-seed", "seed": "seed", "series_a": "series-a", "series_b_plus": "series-b"}
ROUND_TYPES = {**STAGES, "other": "equity"}
PLACEHOLDERS = ("", UNKNOWN, "unknown")  # profile values the agent may replace
MAX_EXTRA_URLS = 3
TIMESTAMP = "%Y-%m-%d %H:%M:%S"  # SQLite datetime('now') format, UTC


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
    created: bool  # a new startup
    assessment_id: int | None  # the stored score
    skipped: str = ""  # why no score was stored (not accepted, already stored)
    kpis: list[str] = field(default_factory=list)


# --- scores in the assessments table (also used by the Backend) -------------------------------------


def has_score(conn: sqlite3.Connection, entity_id: int) -> bool:
    """Whether the startup has an assessment with all six KTH levels (from any engine)."""
    return conn.execute(f"SELECT 1 FROM assessments WHERE entity_id = ? AND {HAS_LEVELS}", (entity_id,)).fetchone() is not None


def missing_levels(conn: sqlite3.Connection, entity_id: int) -> list[str]:
    """Dimensions the startup's latest score has no evidence for (the agent stored them as 1); [] without a score."""
    row = conn.execute(
        f"SELECT levels_basis FROM assessments WHERE entity_id = ? AND {HAS_LEVELS} ORDER BY assessed_at DESC, id DESC LIMIT 1",
        (entity_id,),
    ).fetchone()
    basis = json.loads(row[0]) if row and row[0] else {}
    return [d for d in DIMENSIONS if d in basis and basis[d]["level"] is None]


def needs_score(conn: sqlite3.Connection, entity_id: int) -> bool:
    """No score yet, or the latest has no evidence for TRL or BRL."""
    return not has_score(conn, entity_id) or any(d in REQUIRED_LEVELS for d in missing_levels(conn, entity_id))


def researched_at(conn: sqlite3.Connection, entity_id: int) -> str | None:
    """When the agent last researched the startup (UTC), whatever the judge decided."""
    return conn.execute("SELECT MAX(assessed_at) FROM assessments WHERE entity_id = ? AND engine = ?", (entity_id, ENGINE)).fetchone()[0]


def researched_within(conn: sqlite3.Connection, entity_id: int, days: int) -> str | None:
    """When the agent last researched the startup, if that was in the last ``days``."""
    ran = researched_at(conn, entity_id)
    return ran if ran and ran >= (datetime.now(timezone.utc) - timedelta(days=days)).strftime(TIMESTAMP) else None


def facts_of(conn: sqlite3.Connection, entity_id: int, *, today: str | None = None) -> Facts:
    """The startup's current facts as the agent scores them: fields of its schema with valid values, list fields merged,
    the strongest fact for the others, and derived fields (stage, total_raised, ...) computed from them, not read."""
    facts: Facts = {}
    rows = conn.execute("SELECT * FROM facts WHERE entity_id = ? AND is_current = 1 ORDER BY id", (entity_id,)).fetchall()
    for r in rows:
        spec = FIELDS_BY_NAME.get(r["field"])
        if spec is None or spec.origin == "derived":
            continue
        try:
            found = coerce(spec, json.loads(r["value"]) if r["value"] else None)
        except (InvalidValue, ValueError):
            continue  # a value outside the agent's vocabulary: the rubric can't read it
        if found is None:
            continue
        fact = Fact(r["field"], found, r["evidence"] or "", r["source_url"] or "", r["source_type"], r["retrieved_at"] or "", r["status"],
                    r["confidence"])
        facts[r["field"]] = merge_facts(facts.get(r["field"]), [fact] if spec.is_list else fact)
    website = conn.execute("SELECT website FROM entities WHERE id = ?", (entity_id,)).fetchone()
    today = today or datetime.now(timezone.utc).strftime("%Y-%m-%d")
    derived = derive_all(facts, website_domain=domain(website[0] if website else None), today=today)
    return {k: v for k, v in {**facts, **derived}.items() if v is not None}


def scores_of(conn: sqlite3.Connection, entity_id: int, weights: dict[str, float] | None = None) -> dict[str, Any]:
    """The startup's Investment Score Matrix by the agent's rubric: its latest accepted assessment ("agent"), else the
    rubric with ``weights`` (the agent's [weights]) applied to facts_of ("facts")."""
    row = conn.execute(
        "SELECT * FROM assessments WHERE entity_id = ? AND engine = ? AND trl IS NOT NULL ORDER BY assessed_at DESC, id DESC LIMIT 1",
        (entity_id, ENGINE),
    ).fetchone()
    if row:
        basis = json.loads(row["levels_basis"]) if row["levels_basis"] else {}
        level = lambda name: (basis.get(name) or {}).get("level")  # noqa: E731
        return {"source": "agent", "assessed_at": row["assessed_at"], "trl": level("trl"), "brl": level("brl"),
                "ocean_impact_readiness": level("oir"), "criteria": json.loads(row["criteria"]) if row["criteria"] else [],
                "investment_score": row["investment_score"], "investment_percent": investment_percent(row["investment_score"]),
                "overall_confidence": row["overall_confidence"]}
    scores = score_all(facts_of(conn, entity_id), weights)
    return {"source": "facts", "assessed_at": None, "trl": scores.trl.level, "brl": scores.brl.level,
            "ocean_impact_readiness": scores.ocean_impact_readiness.level, "criteria": [asdict(c) for c in scores.criteria],
            "investment_score": scores.investment_score, "investment_percent": scores.investment_percent,
            "overall_confidence": scores.overall_confidence}


class StartupDatabase:
    def __init__(self, path: Path):
        self.path = path

    def connect(self) -> sqlite3.Connection:
        if not self.path.exists():
            raise AgentError(f"database not found: {self.path}")
        conn = sqlite3.connect(self.path, timeout=30)
        conn.row_factory = sqlite3.Row
        conn.execute("PRAGMA foreign_keys = ON")
        tables = {r[0] for r in conn.execute("SELECT name FROM sqlite_master WHERE type = 'table'")}
        if missing := {"entities", "facts", "assessments"} - tables:
            conn.close()
            raise AgentError(f"{self.path} has no {', '.join(sorted(missing))} table: use the unified database (DB/startupgo_unified.db)")
        return conn

    # --- reading -------------------------------------------------------------------------------

    def pending(self, *, limit: int, max_age_days: int, slugs: tuple[str, ...] = ()) -> list[Candidate]:
        """Startups with a website that need a score and weren't researched in ``max_age_days``; ``slugs`` picks them instead."""
        conn = self.connect()
        try:
            sql = f"""SELECT e.id, e.slug, e.name, e.website,
                             (SELECT MAX(assessed_at) FROM assessments a WHERE a.entity_id = e.id AND a.engine = '{ENGINE}') AS ran
                      FROM entities e WHERE e.kind = 'startup' AND e.website IS NOT NULL AND e.website != ''"""
            if slugs:
                rows = conn.execute(f"{sql} AND e.slug IN ({', '.join('?' * len(slugs))}) ORDER BY e.id", slugs).fetchall()
            else:
                rows = [r for r in conn.execute(f"{sql} ORDER BY ran IS NOT NULL, ran, e.id")
                        if needs_score(conn, r["id"]) and not researched_within(conn, r["id"], max_age_days)]
            return [self._candidate(conn, row) for row in rows[:limit]]
        finally:
            conn.close()

    def _candidate(self, conn: sqlite3.Connection, row: sqlite3.Row) -> Candidate:
        business_id = conn.execute(
            "SELECT value FROM facts WHERE entity_id = ? AND field = 'business_id' AND is_current = 1 ORDER BY confidence DESC, id LIMIT 1",
            (row["id"],),
        ).fetchone()
        own = domain(row["website"])
        urls = [r[0] for r in conn.execute(
            "SELECT source_url FROM facts WHERE entity_id = ? AND field = 'reference' AND source_url IS NOT NULL ORDER BY id", (row["id"],))]
        extra = tuple(u for u in dict.fromkeys(urls) if domain(u) and domain(u) != own)[:MAX_EXTRA_URLS]
        return Candidate(row["name"], row["website"], slug=row["slug"], business_id=json.loads(business_id[0]) if business_id else None,
                         extra_urls=extra)

    def known_domains(self) -> dict[str, str]:
        """Website domain -> slug of every database startup."""
        conn = self.connect()
        try:
            return {d: r["slug"] for r in conn.execute("SELECT slug, website FROM entities WHERE kind = 'startup'") if (d := domain(r["website"]))}
        finally:
            conn.close()

    # --- writing -------------------------------------------------------------------------------

    def save(self, entry: dict[str, Any], *, slug: str | None = None) -> Stored:
        """Store an evaluated, judge-reviewed entry (``StartupRecord.to_dict()``); ``slug`` pins the startup."""
        status = (entry.get("review") or {}).get("status")
        accepted = status in ACCEPTED
        record = StartupRecord.from_dict(entry)
        assessed_at = _utc(entry["generated_at"])
        conn = self.connect()
        try:
            with conn:  # one transaction: committed on return, rolled back on an error
                found = self._find(conn, entry["website"], slug)
                skipped = "" if accepted else f"judge status {status or 'missing'}"
                if not accepted and (found is None or status is None):  # a new startup, or an entry the judge never saw
                    return Stored(found["slug"] if found else "", False, None, skipped=skipped)
                if found is not None and (known := conn.execute(
                        "SELECT id, trl FROM assessments WHERE entity_id = ? AND engine = ? AND assessed_at = ?",
                        (found["id"], ENGINE, assessed_at)).fetchone()):
                    return Stored(found["slug"], False, known["id"] if known["trl"] is not None else None, skipped="entry already stored")
                if not accepted:
                    self._assessment(conn, found["id"], entry, record.facts, assessed_at, accepted=False)
                    return Stored(found["slug"], False, None, skipped=skipped)
                entity_id, slug, created = self._startup(conn, found, entry, record.facts)
                assessment_id = self._assessment(conn, entity_id, entry, record.facts, assessed_at, accepted=True)
                self._facts(conn, entity_id, entry)
                kpis = self._kpis(conn, entity_id, record.facts, assessed_at)
                self._sources(conn, entity_id, entry.get("sources", []))
                return Stored(slug, created, assessment_id, kpis=kpis)
        finally:
            conn.close()

    def save_run(self, *, name: str, website: str, retrievals: list[Retrieval], started_at: str, entry_id: str | None = None,
                 slug: str | None = None, error: str | None = None) -> int | None:
        """Log one research run and what it retrieved (agent_runs, agent_retrievals); None when the database has no such tables.

        ``slug`` is the startup the run was about; retrievals whose URL a stored fact cites are marked used.
        """
        conn = self.connect()
        try:
            if not {"agent_runs", "agent_retrievals"} <= {r[0] for r in conn.execute("SELECT name FROM sqlite_master WHERE type = 'table'")}:
                return None
            with conn:
                row = conn.execute("SELECT id FROM entities WHERE kind = 'startup' AND slug = ?", (slug,)).fetchone() if slug else None
                run_id = conn.execute(
                    "INSERT INTO agent_runs (entity_id, name, website, status, started_at, finished_at, entry_id, error)"
                    " VALUES (?, ?, ?, ?, ?, datetime('now'), ?, ?)",
                    (row["id"] if row else None, name, website, "error" if error else "ok", started_at, entry_id, error)).lastrowid
                conn.executemany(
                    "INSERT INTO agent_retrievals (run_id, seq, kind, url, query, provider, source_type, status, detail, retrieved_at)"
                    " VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)",
                    [(run_id, i, r.kind, r.url, r.query, r.provider, r.source_type, r.status, r.detail, r.retrieved_at)
                     for i, r in enumerate(retrievals, 1)])
                if row:
                    conn.execute(
                        "UPDATE agent_retrievals SET used = 1 WHERE run_id = ? AND url IN"
                        " (SELECT source_url FROM facts WHERE entity_id = ? AND is_current = 1 AND source_url IS NOT NULL)",
                        (run_id, row["id"]))
            return run_id
        finally:
            conn.close()

    def add_scraped(self, record: dict[str, Any], *, website: str | None = None) -> dict[str, Any]:
        """A startup record from the scrape agent as a sourced startup (no score yet), plus the record as evidence.

        ``website`` overrides the record's. Returns slug, name and status: "created", "promoted" (a BlueInvest candidate
        became a startup) or "exists" (the record is added to that startup's evidence). Adding the same record twice adds
        its evidence once.
        """
        site = (website or record.get("website") or "").strip()
        name = (record.get("title") or "").strip()
        if not name or not domain(site):
            raise AgentError("a startup needs a name and a website")
        site = site if "//" in site else f"https://{site}"
        fields = {a["name"]: a["value"] for a in record.get("attributes") or [] if a.get("name") and a.get("value")}
        conn = self.connect()
        try:
            row = self._find(conn, site, None)
            if row is not None and row["kind"] == "startup":
                entity_id, slug, status = row["id"], row["slug"], "exists"
            elif row is not None:
                slug = row["slug"] or _unique_slug(conn, row["name"])
                conn.execute("UPDATE entities SET kind = 'startup', slug = ?, pipeline_stage = 'sourced', updated_at = datetime('now') "
                             "WHERE id = ?", (slug, row["id"]))
                entity_id, status = row["id"], "promoted"
            else:
                slug = _unique_slug(conn, name)
                details = (record.get("details") or "").strip()
                cols = {
                    "key": f"startup:{slug}", "kind": "startup", "slug": slug, "pipeline_stage": "sourced", "name": name,
                    "website": site, "domain": domain(site), "tagline": (fields.get("what_it_does") or details or name)[:200],
                    "description": details or name, "sector": fields.get("sector") or UNKNOWN, "country": fields.get("country") or UNKNOWN,
                    "city": fields.get("city"), "stage": "unknown",
                }
                cur = conn.execute(f"INSERT INTO entities ({', '.join(cols)}) VALUES ({', '.join('?' * len(cols))})", tuple(cols.values()))
                entity_id, status = cur.lastrowid, "created"
            value = {k: record.get(k) for k in ("kind", "title", "details", "group", "self_reported")} | {"attributes": fields}
            evidence, source_url = (record.get("quote") or "")[:2000], record.get("source_url") or None
            seen = conn.execute("SELECT 1 FROM facts WHERE entity_id = ? AND source_name = ? AND field = 'scraped_record' AND evidence = ? "
                                "AND source_url IS ?", (entity_id, SCRAPER, evidence, source_url)).fetchone()
            if not seen:
                verified = record.get("evidence") == "page"
                independent = verified and not record.get("self_reported") and domain(source_url) != domain(site)
                conn.execute(
                    """INSERT INTO facts (entity_id, section, field, value, evidence, source_url, source_type, source_name, status,
                                          confidence, retrieved_at)
                       VALUES (?, 'Api', 'scraped_record', ?, ?, ?, ?, ?, ?, ?, date('now'))""",
                    (entity_id, _json(value), evidence, source_url, "website" if domain(source_url) == domain(site) else "news", SCRAPER,
                     "verified" if independent else "claimed" if verified else "inferred", 0.7 if independent else 0.5 if verified else 0.3),
                )
            conn.commit()
            return {"slug": slug, "name": row["name"] if row is not None else name, "status": status}
        finally:
            conn.close()

    def _find(self, conn: sqlite3.Connection, website: str, slug: str | None) -> sqlite3.Row | None:
        if slug:
            row = conn.execute("SELECT * FROM entities WHERE kind = 'startup' AND slug = ?", (slug,)).fetchone()
            if row is None:
                raise AgentError(f"no startup with slug {slug!r} in {self.path}")
            return row
        own = domain(website)
        rows = conn.execute("SELECT * FROM entities WHERE kind IN ('startup', 'candidate') AND website IS NOT NULL ORDER BY kind != 'startup', id")
        return next((r for r in rows if own and (r["domain"] or domain(r["website"])) == own), None)

    def _startup(self, conn: sqlite3.Connection, row: sqlite3.Row | None, entry: dict[str, Any], facts: Facts) -> tuple[int, str, bool]:
        """The startup's entity id, slug and whether it is new: fills blank profile fields, turns a candidate into a startup."""
        profile = _profile(entry, facts)
        if row is None:
            slug = _unique_slug(conn, entry["name"])
            cols = {"key": f"startup:{slug}", "kind": "startup", "slug": slug, "pipeline_stage": "sourced", **profile}
            cur = conn.execute(f"INSERT INTO entities ({', '.join(cols)}) VALUES ({', '.join('?' * len(cols))})", tuple(cols.values()))
            return cur.lastrowid, slug, True
        updates = {k: v for k, v in profile.items() if row[k] in (*PLACEHOLDERS, None) and v not in (*PLACEHOLDERS, None)}
        created = row["kind"] == "candidate"
        if created:  # a BlueInvest lead the judge accepted: now a startup
            updates |= {"kind": "startup", "slug": row["slug"] or _unique_slug(conn, row["name"]), "pipeline_stage": "sourced"}
        if updates:
            sets = ", ".join(f"{k} = ?" for k in updates)
            conn.execute(f"UPDATE entities SET {sets}, updated_at = datetime('now') WHERE id = ?", (*updates.values(), row["id"]))
        return row["id"], updates.get("slug") or row["slug"], created

    def _assessment(self, conn: sqlite3.Connection, entity_id: int, entry: dict[str, Any], facts: Facts, assessed_at: str,
                    *, accepted: bool) -> int:
        scores = entry["scores"]
        basis = {"trl": scores["trl"], "brl": scores["brl"], **{k: asdict(v) for k, v in score_kth(facts).items()},
                 "oir": scores["ocean_impact_readiness"]}
        unknown = [d.upper() for d in DIMENSIONS if basis[d]["level"] is None]
        review = entry.get("review") or {}
        issues = len(review.get("open_issues", []))
        rationale = "; ".join([
            *(f"{d.upper()} {basis[d]['level']}: {basis[d]['basis'][0]}" for d in DIMENSIONS if basis[d]["level"] is not None),
            *([f"no evidence for {', '.join(unknown)}" + (" (stored as 1)" if accepted else "")] if unknown else []),
            f"judge {review.get('status')}" + (f" with {issues} open issue(s)" if issues else ""),
            f"agent entry {entry['id']}",
        ])
        levels = {d: (basis[d]["level"] or 1) if accepted else None for d in DIMENSIONS}
        kpis = {k.code: {"level": k.level, "claim": k.claim, "source_url": k.source_url} for k in ocean_kpis(facts)}
        cols = {
            "entity_id": entity_id, "assessed_at": assessed_at, "engine": ENGINE, "assessor": ASSESSOR,
            "confidence": confidence_label(scores["overall_confidence"]), **levels,
            "oir": basis["oir"]["level"] if accepted else None,
            "levels_basis": _json(basis), "navigator_kpis": _json(kpis), "criteria": _json(scores["criteria"]),
            "investment_score": scores["investment_score"] if accepted else None,
            "overall_confidence": scores["overall_confidence"] if accepted else None,
            "data_gaps": _json(entry.get("data_gaps", [])), "next_steps": _json(entry.get("next_steps", [])),
            "rationale": rationale[:2000], "judge_status": review.get("status"),
        }
        cur = conn.execute(f"INSERT INTO assessments ({', '.join(cols)}) VALUES ({', '.join('?' * len(cols))})", tuple(cols.values()))
        return cur.lastrowid

    def _facts(self, conn: sqlite3.Connection, entity_id: int, entry: dict[str, Any]) -> None:
        """The entry's facts in place of the agent's earlier ones; rounds also carry the funding_rounds view's keys."""
        conn.execute("UPDATE facts SET is_current = 0 WHERE entity_id = ? AND source_name = ? AND field NOT IN ('navigator_kpi', 'reference')",
                     (entity_id, ENGINE))
        rounds = {tuple(r) for r in conn.execute(
            "SELECT json_extract(value, '$.round_type'), json_extract(value, '$.announced_on') FROM facts "
            "WHERE entity_id = ? AND field IN ('equity_rounds', 'grants') AND is_current = 1 AND json_extract(value, '$.round_type') IS NOT NULL",
            (entity_id,))}
        for section_id, section in entry["sections"].items():
            for name, found in section["facts"].items():
                if name == "last_changed" or found is None:
                    continue
                for fact in found if isinstance(found, list) else [found]:
                    current = True
                    if name in ("equity_rounds", "grants"):
                        fact = {**fact, "value": _round(name, fact)}
                        key = (fact["value"]["round_type"], fact["value"]["announced_on"])
                        current = key not in rounds
                        rounds.add(key)
                    _insert_fact(conn, entity_id, section_id, fact, current=current)

    def _kpis(self, conn: sqlite3.Connection, entity_id: int, facts: Facts, assessed_at: str) -> list[str]:
        """Navigator KPI evidence; a KPI is replaced only by a higher level."""
        found = ocean_kpis(facts)
        for kpi in found:
            stored = conn.execute(
                "SELECT MAX(json_extract(value, '$.level')) FROM facts WHERE entity_id = ? AND field = 'navigator_kpi' AND is_current = 1 "
                "AND json_extract(value, '$.kpi') = ?", (entity_id, kpi.code)).fetchone()[0]
            if stored is not None and kpi.level <= stored:
                continue
            conn.execute("UPDATE facts SET is_current = 0 WHERE entity_id = ? AND field = 'navigator_kpi' AND json_extract(value, '$.kpi') = ?",
                         (entity_id, kpi.code))
            _insert_fact(conn, entity_id, "Api", {
                "field": "navigator_kpi", "value": {"kpi": kpi.code, "level": kpi.level, "claim": kpi.claim}, "evidence": kpi.claim,
                "source_url": kpi.source_url, "source_type": "manual", "retrieved_at": assessed_at[:10], "status": "inferred",
                "confidence": INFERRED_CONFIDENCE,
            })
        return [k.code for k in found]

    def _sources(self, conn: sqlite3.Connection, entity_id: int, sources: list[dict[str, Any]]) -> None:
        stored = {r[0] for r in conn.execute("SELECT source_url FROM facts WHERE entity_id = ? AND field = 'reference'", (entity_id,))}
        for source in sources:
            if (url := source.get("url")) and url not in stored:
                stored.add(url)
                title = source.get("title") or url
                _insert_fact(conn, entity_id, "Api", {
                    "field": "reference", "value": {"title": title}, "evidence": title, "source_url": url, "source_type": "website",
                    "retrieved_at": source.get("retrieved_at"), "status": "claimed", "confidence": INFERRED_CONFIDENCE,
                })


def _insert_fact(conn: sqlite3.Connection, entity_id: int, section: str, fact: dict[str, Any], *, current: bool = True) -> None:
    """A fact in the agent's format (facts.Fact.to_dict()) as a facts row."""
    conn.execute(
        """INSERT INTO facts (entity_id, section, field, value, evidence, source_url, source_type, source_name, status, confidence,
                              retrieved_at, observed_on, is_current)
           VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)""",
        (entity_id, section, fact["field"], _json(fact["value"]), (fact.get("evidence") or "")[:2000], fact.get("source_url") or None,
         fact["source_type"], ENGINE, fact["status"], fact["confidence"], fact.get("retrieved_at"), _observed(fact["value"]), int(current)),
    )


def _round(name: str, fact: dict[str, Any]) -> dict[str, Any]:
    """A round or grant value plus the keys the funding_rounds view reads (round_type, announced_on, lead_investors, notes)."""
    v = fact["value"]
    currency = v.get("currency")
    currency = currency.upper() if isinstance(currency, str) and re.fullmatch(r"[A-Za-z]{3}", currency) else None
    if name == "grants":
        view = {"round_type": "grant", "announced_on": str(v["year"]) if v.get("year") else None, "lead_investors": v.get("funder")}
    else:
        view = {"round_type": ROUND_TYPES.get(v.get("stage") or "other", "equity"), "announced_on": v.get("date"),
                "lead_investors": ", ".join(v.get("investors") or []) or None}
    return {**v, **view, "currency": currency, "notes": f"{ASSESSOR}: {fact.get('evidence') or ''}"[:500]}


def _observed(value: Any) -> str | None:
    """When the fact was true, if its value says (a round's date, a grant's year)."""
    if isinstance(value, dict):
        when = value.get("date") or value.get("announced_on") or value.get("year")
        return str(when) if when else None
    return None


def _profile(entry: dict[str, Any], facts: Facts) -> dict[str, Any]:
    """The startup's entity columns the entry describes; unknown required fields are "Unknown"."""
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
        "blue_sector": sector,
        "country": value(facts, "country") or UNKNOWN,
        "city": value(facts, "city"),
        "founded_year": int(founded) if founded.isdigit() else None,
        "website": entry["website"],
        "domain": domain(entry["website"]) or None,
        "stage": STAGES.get(stage, "unknown") if stage != "grant_only" else "pre-seed",
    }


def _unique_slug(conn: sqlite3.Connection, name: str) -> str:
    base = slug = slugify(name)
    n = 2
    while conn.execute("SELECT 1 FROM entities WHERE slug = ?", (slug,)).fetchone():
        slug, n = f"{base}-{n}", n + 1
    return slug


def _utc(timestamp: str) -> str:
    """An ISO timestamp as UTC in SQLite's datetime('now') format (naive ones are taken as UTC)."""
    when = datetime.fromisoformat(timestamp)
    return (when if when.tzinfo else when.replace(tzinfo=timezone.utc)).astimezone(timezone.utc).strftime(TIMESTAMP)


def _json(data: Any) -> str:
    return json.dumps(data, ensure_ascii=False, default=str)


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
