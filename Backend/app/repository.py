"""Data access: SQL queries that assemble startups with their scores."""

import re
import sqlite3
from dataclasses import asdict
from datetime import date

from . import scoring
from .schemas import (
    AssessmentCreate,
    FundingRound,
    LevelDetail,
    Note,
    OceanKpiEvidence,
    Readiness,
    Scores,
    ScorePreviewRequest,
    SearchFilters,
    Source,
    StartupCreate,
    StartupDetail,
    StartupSummary,
)


class InvalidInput(ValueError):
    """Raised for requests that pass schema validation but conflict with stored data."""

LATEST_ASSESSMENT_SQL = """
SELECT * FROM readiness_assessments
WHERE startup_id = ?
ORDER BY assessed_on DESC, id DESC
LIMIT 1
"""


def _rounds(conn: sqlite3.Connection, startup_id: int) -> list[FundingRound]:
    rows = conn.execute(
        "SELECT * FROM funding_rounds WHERE startup_id = ? ORDER BY announced_on DESC NULLS LAST, id DESC",
        (startup_id,),
    ).fetchall()
    return [
        FundingRound(
            round_type=r["round_type"],
            amount=r["amount"],
            currency=r["currency"],
            amount_usd=scoring.to_usd(r["amount"], r["currency"]),
            announced_on=r["announced_on"],
            lead_investors=r["lead_investors"],
            notes=r["notes"],
            source_url=r["source_url"],
        )
        for r in rows
    ]


def _kpi_pairs(conn: sqlite3.Connection, startup_id: int) -> list[tuple[str, int]]:
    rows = conn.execute(
        "SELECT kpi_code, evidence_level FROM startup_ocean_kpis WHERE startup_id = ?", (startup_id,)
    ).fetchall()
    return [(r["kpi_code"], r["evidence_level"]) for r in rows]


def _summary(conn: sqlite3.Connection, row: sqlite3.Row) -> StartupSummary:
    assessment = conn.execute(LATEST_ASSESSMENT_SQL, (row["id"],)).fetchone()
    readiness = Readiness(**{k: assessment[k] for k in Readiness.model_fields})
    levels = {d: assessment[d] for d in scoring.DIMENSIONS}

    rounds = _rounds(conn, row["id"])
    dated = [r.announced_on for r in rounds if r.announced_on]
    last_round_on = max(dated) if dated else None
    disclosed = [r.amount_usd for r in rounds if r.amount_usd is not None]

    breakdown = scoring.score_startup(
        levels,
        _kpi_pairs(conn, row["id"]),
        row["stage"],
        scoring.parse_partial_date(last_round_on),
    )
    return StartupSummary(
        slug=row["slug"],
        name=row["name"],
        tagline=row["tagline"],
        description=row["description"],
        sector=row["sector"],
        country=row["country"],
        city=row["city"],
        stage=row["stage"],
        pipeline_stage=row["pipeline_stage"],
        readiness=readiness,
        scores=Scores(**asdict(breakdown)),
        total_disclosed_usd=sum(disclosed) if disclosed else None,
        last_round_on=last_round_on,
    )


def summaries(conn: sqlite3.Connection, slugs: list[str]) -> dict[str, StartupSummary]:
    """Summaries of the given startups by slug; unknown slugs are left out."""
    if not slugs:
        return {}
    marks = ", ".join("?" * len(slugs))
    rows = conn.execute(f"SELECT * FROM startups WHERE slug IN ({marks})", slugs).fetchall()
    return {r["slug"]: _summary(conn, r) for r in rows}


def passes(summary: StartupSummary, f: SearchFilters) -> bool:
    """Whether a startup matches the filters (same meaning as list_startups' parameters)."""
    profile = (("sector", f.sector), ("country", f.country), ("stage", f.stage), ("pipeline_stage", f.pipeline_stage))
    return (
        all(v is None or getattr(summary, k) == v for k, v in profile)
        and (f.impact_area is None or f.impact_area in summary.scores.ocean_areas_covered)
        and (f.min_trl is None or summary.readiness.trl >= f.min_trl)
        and (f.min_brl is None or summary.readiness.brl >= f.min_brl)
        and (f.min_potential is None or summary.scores.potential >= f.min_potential)
    )


def entry_passes(trl: int | None, brl: int | None, f: SearchFilters) -> bool:
    """Agent-only entries know only TRL and BRL: any other filter leaves them out."""
    if any(v is not None for v in (f.sector, f.country, f.stage, f.pipeline_stage, f.impact_area, f.min_potential)):
        return False
    return (f.min_trl is None or (trl or 0) >= f.min_trl) and (f.min_brl is None or (brl or 0) >= f.min_brl)


SORT_KEYS = {
    "potential": lambda s: -s.scores.potential,
    "readiness": lambda s: -s.scores.readiness,
    "ocean": lambda s: -s.scores.ocean_impact,
    "momentum": lambda s: -s.scores.momentum,
    "trl": lambda s: -s.readiness.trl,
    "brl": lambda s: -s.readiness.brl,
    "name": lambda s: s.name.lower(),
}


def list_startups(
    conn: sqlite3.Connection,
    *,
    q: str | None = None,
    sector: str | None = None,
    country: str | None = None,
    stage: str | None = None,
    pipeline_stage: str | None = None,
    impact_area: str | None = None,
    min_trl: int | None = None,
    min_brl: int | None = None,
    min_potential: float | None = None,
    sort: str = "potential",
) -> list[StartupSummary]:
    clauses, params = [], []
    if q:
        # Simple keyword search for now; natural-language parsing comes later.
        for term in q.split():
            like = f"%{term}%"
            clauses.append(
                "(name LIKE ? OR tagline LIKE ? OR description LIKE ? OR sector LIKE ? OR country LIKE ? OR city LIKE ?)"
            )
            params += [like] * 6
    for column, value in (("sector", sector), ("country", country), ("stage", stage), ("pipeline_stage", pipeline_stage)):
        if value:
            clauses.append(f"{column} = ?")
            params.append(value)
    if impact_area:
        clauses.append(
            "id IN (SELECT startup_id FROM startup_ocean_kpis k JOIN ocean_kpis o ON o.code = k.kpi_code "
            "WHERE o.area_code = ? AND k.evidence_level > 0)"
        )
        params.append(impact_area)

    where = f"WHERE {' AND '.join(clauses)}" if clauses else ""
    rows = conn.execute(f"SELECT * FROM startups {where}", params).fetchall()
    results = [_summary(conn, r) for r in rows]

    if min_trl is not None:
        results = [s for s in results if s.readiness.trl >= min_trl]
    if min_brl is not None:
        results = [s for s in results if s.readiness.brl >= min_brl]
    if min_potential is not None:
        results = [s for s in results if s.scores.potential >= min_potential]

    results.sort(key=SORT_KEYS.get(sort, SORT_KEYS["potential"]))
    return results


def get_startup(conn: sqlite3.Connection, slug: str) -> StartupDetail | None:
    row = conn.execute("SELECT * FROM startups WHERE slug = ?", (slug,)).fetchone()
    if row is None:
        return None
    summary = _summary(conn, row)

    level_rows = conn.execute(
        "SELECT dimension_code, level, summary FROM readiness_levels"
    ).fetchall()
    level_text = {(r["dimension_code"], r["level"]): r["summary"] for r in level_rows}
    dims = conn.execute("SELECT code, name FROM readiness_dimensions ORDER BY sort_order").fetchall()
    levels = []
    for d in dims:
        current = getattr(summary.readiness, d["code"].lower())
        levels.append(
            LevelDetail(
                dimension=d["code"],
                name=d["name"],
                level=current,
                summary=level_text[(d["code"], current)],
                next_summary=level_text.get((d["code"], current + 1)),
            )
        )

    kpi_rows = conn.execute(
        """
        SELECT k.kpi_code, o.name AS kpi_name, a.code AS area_code, a.name AS area_name,
               k.evidence_level, k.claim, k.source_url
        FROM startup_ocean_kpis k
        JOIN ocean_kpis o ON o.code = k.kpi_code
        JOIN ocean_impact_areas a ON a.code = o.area_code
        WHERE k.startup_id = ?
        ORDER BY k.evidence_level DESC, k.kpi_code
        """,
        (row["id"],),
    ).fetchall()
    ocean_kpis = [
        OceanKpiEvidence(**dict(r), evidence_label=scoring.EVIDENCE_LABELS[r["evidence_level"]]) for r in kpi_rows
    ]

    sources = [Source(title=r["title"], url=r["url"]) for r in conn.execute(
        "SELECT title, url FROM sources WHERE startup_id = ? ORDER BY id", (row["id"],)
    )]
    notes = [Note(**dict(r)) for r in conn.execute(
        "SELECT id, author, body, created_at FROM notes WHERE startup_id = ? ORDER BY created_at DESC, id DESC",
        (row["id"],),
    )]

    return StartupDetail(
        **summary.model_dump(),
        founded_year=row["founded_year"],
        website=row["website"],
        levels=levels,
        ocean_kpis=ocean_kpis,
        funding_rounds=_rounds(conn, row["id"]),
        sources=sources,
        notes=notes,
    )


def set_pipeline_stage(conn: sqlite3.Connection, slug: str, stage: str) -> bool:
    cur = conn.execute(
        "UPDATE startups SET pipeline_stage = ?, updated_at = datetime('now') WHERE slug = ?", (stage, slug)
    )
    conn.commit()
    return cur.rowcount > 0


def add_note(conn: sqlite3.Connection, slug: str, body: str, author: str) -> Note | None:
    row = conn.execute("SELECT id FROM startups WHERE slug = ?", (slug,)).fetchone()
    if row is None:
        return None
    cur = conn.execute("INSERT INTO notes (startup_id, author, body) VALUES (?, ?, ?)", (row["id"], author, body))
    conn.commit()
    note = conn.execute("SELECT id, author, body, created_at FROM notes WHERE id = ?", (cur.lastrowid,)).fetchone()
    return Note(**dict(note))


def filter_options(conn: sqlite3.Connection) -> dict:
    def distinct(column: str) -> list[str]:
        return [r[0] for r in conn.execute(f"SELECT DISTINCT {column} FROM startups ORDER BY {column}")]

    return {
        "sectors": distinct("sector"),
        "countries": distinct("country"),
        "stages": distinct("stage"),
        "pipeline_stages": ["sourced", "screening", "diligence", "term-sheet", "portfolio", "passed"],
        "impact_areas": [dict(r) for r in conn.execute("SELECT code, name FROM ocean_impact_areas ORDER BY code")],
    }


def frameworks(conn: sqlite3.Connection) -> dict:
    dims = []
    for d in conn.execute("SELECT * FROM readiness_dimensions ORDER BY sort_order").fetchall():
        levels = conn.execute(
            "SELECT level, summary FROM readiness_levels WHERE dimension_code = ? ORDER BY level", (d["code"],)
        ).fetchall()
        dims.append({**dict(d), "weight": scoring.READINESS_WEIGHTS[d["code"].lower()], "levels": [dict(l) for l in levels]})

    areas = []
    for a in conn.execute("SELECT * FROM ocean_impact_areas ORDER BY code").fetchall():
        kpis = conn.execute(
            "SELECT code, name, qualitative_only FROM ocean_kpis WHERE area_code = ? ORDER BY code", (a["code"],)
        ).fetchall()
        areas.append({**dict(a), "kpis": [dict(k) for k in kpis]})

    return {
        "readiness_dimensions": dims,
        "ocean_impact_areas": areas,
        "evidence_scale": [{"level": k, "label": v} for k, v in scoring.EVIDENCE_LABELS.items()],
        "potential_weights": scoring.POTENTIAL_WEIGHTS,
        "max_healthy_spread": scoring.MAX_HEALTHY_SPREAD,
        "penalty_per_extra_level": scoring.PENALTY_PER_EXTRA_LEVEL,
    }


# ---------------------------------------------------------------------------
# Writes: assessments and new startups
# ---------------------------------------------------------------------------


def _slugify(name: str) -> str:
    return re.sub(r"[^a-z0-9]+", "-", name.lower()).strip("-") or "startup"


def _unique_slug(conn: sqlite3.Connection, name: str) -> str:
    base = slug = _slugify(name)
    n = 2
    while conn.execute("SELECT 1 FROM startups WHERE slug = ?", (slug,)).fetchone():
        slug = f"{base}-{n}"
        n += 1
    return slug


def _insert_assessment(conn: sqlite3.Connection, startup_id: int, a: AssessmentCreate) -> None:
    """Store a dated readiness snapshot and replace the startup's ocean KPI evidence."""
    codes = [k.kpi_code for k in a.ocean_kpis]
    if len(codes) != len(set(codes)):
        raise InvalidInput("Each ocean KPI may appear only once")
    known = {r[0] for r in conn.execute("SELECT code FROM ocean_kpis")}
    if unknown := sorted(set(codes) - known):
        raise InvalidInput(f"Unknown ocean KPI codes: {', '.join(unknown)}")

    conn.execute(
        """
        INSERT INTO readiness_assessments
            (startup_id, assessed_on, assessor, confidence, crl, trl, brl, iprl, tmrl, frl, rationale)
        VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        """,
        (startup_id, date.today().isoformat(), a.assessor, a.confidence,
         a.crl, a.trl, a.brl, a.iprl, a.tmrl, a.frl, a.rationale),
    )
    conn.execute("DELETE FROM startup_ocean_kpis WHERE startup_id = ?", (startup_id,))
    conn.executemany(
        "INSERT INTO startup_ocean_kpis (startup_id, kpi_code, evidence_level, claim, source_url) VALUES (?, ?, ?, ?, ?)",
        [
            (startup_id, k.kpi_code, k.evidence_level, k.claim.strip(), k.source_url or None)
            for k in a.ocean_kpis
            if k.evidence_level > 0
        ],
    )
    conn.execute("UPDATE startups SET updated_at = datetime('now') WHERE id = ?", (startup_id,))


def add_assessment(conn: sqlite3.Connection, slug: str, assessment: AssessmentCreate) -> StartupDetail | None:
    row = conn.execute("SELECT id FROM startups WHERE slug = ?", (slug,)).fetchone()
    if row is None:
        return None
    with conn:
        _insert_assessment(conn, row["id"], assessment)
    return get_startup(conn, slug)


def create_startup(conn: sqlite3.Connection, data: StartupCreate) -> StartupDetail:
    slug = _unique_slug(conn, data.name)
    with conn:
        cur = conn.execute(
            """
            INSERT INTO startups (slug, name, tagline, description, sector, country, city, founded_year, website, stage)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
            (slug, data.name.strip(), data.tagline.strip(), data.description.strip(), data.sector.strip(),
             data.country.strip(), data.city, data.founded_year, data.website, data.stage),
        )
        startup_id = cur.lastrowid
        if r := data.funding_round:
            conn.execute(
                """
                INSERT INTO funding_rounds (startup_id, round_type, amount, currency, announced_on, lead_investors)
                VALUES (?, ?, ?, ?, ?, ?)
                """,
                (startup_id, r.round_type, r.amount, r.currency, r.announced_on, r.lead_investors),
            )
        _insert_assessment(conn, startup_id, data.assessment)
    return get_startup(conn, slug)


def preview_scores(req: ScorePreviewRequest) -> Scores:
    levels = {d: getattr(req, d) for d in scoring.DIMENSIONS}
    breakdown = scoring.score_startup(
        levels,
        [(k.kpi_code, k.evidence_level) for k in req.ocean_kpis],
        req.stage,
        scoring.parse_partial_date(req.last_round_on),
    )
    return Scores(**asdict(breakdown))
