"""Investment memo: a one-page-per-section brief on a startup, assembled from the database in one request.

Everything is deterministic: scores, levels and evidence come from the views in DB/unified.sql, the narrative
(recommendation, highlights, risks, next steps) from rules over them, and the agent's own extras (data gaps, next
steps, red flags) from its latest assessments row. No LLM call, so the memo is instant and reproducible.
"""

import json
import sqlite3
from datetime import datetime, timezone
from typing import Any

from . import features_repo, repository
from .schemas import InvestmentMemo, MemoAssessment, MemoNextStep, MemoRecommendation, StartupDetail

MAX_QUESTIONS = 10
UNBALANCED_SPREAD = 4  # levels between the strongest and the weakest KTH dimension

VERDICTS = {  # band (scoring.band_for) -> verdict, tone
    "Strong": ("Advance to due diligence", "positive"),
    "Promising": ("Take a first call", "positive"),
    "Watch": ("Monitor", "neutral"),
    "Early": ("Pass for now", "caution"),
}


def _json(value: str | None) -> list[Any]:
    try:
        data = json.loads(value) if value else []
    except ValueError:
        return []
    return data if isinstance(data, list) else []


def _latest_assessment(conn: sqlite3.Connection, slug: str) -> sqlite3.Row | None:
    """The assessments row behind the startup's current scores (the newest one with all six levels)."""
    return conn.execute(
        """
        SELECT a.* FROM assessments a JOIN all_startups s ON s.id = a.entity_id
        WHERE s.slug = ? AND a.crl IS NOT NULL AND a.trl IS NOT NULL AND a.brl IS NOT NULL
          AND a.iprl IS NOT NULL AND a.tmrl IS NOT NULL AND a.frl IS NOT NULL
        ORDER BY a.assessed_at DESC, a.id DESC LIMIT 1
        """,
        (slug,),
    ).fetchone()


def _recommendation(s: StartupDetail) -> MemoRecommendation:
    if not s.assessed:
        return MemoRecommendation(
            verdict="Research first", tone="neutral",
            rationale="No readiness assessment yet. Open the startup in StartupGo to run the research agent, then regenerate this memo.",
        )
    verdict, tone = VERDICTS.get(s.scores.band, ("Monitor", "neutral"))
    parts = [
        f"Investment potential {s.scores.potential:.0f}/100 ({s.scores.band}): readiness index {s.scores.readiness:.0f}, "
        f"ocean impact {s.scores.ocean_impact:.0f}, funding momentum {s.scores.momentum:.0f}."
    ]
    if s.scores.lagging_dimensions:
        parts.append(f"Lagging: {', '.join(s.scores.lagging_dimensions)}.")
    if s.readiness.confidence == "low" or s.investment.overall_confidence < 0.3:
        parts.append("Evidence confidence is low: validate the levels with the founders before committing.")
        if tone == "positive":
            tone = "neutral"
    return MemoRecommendation(verdict=verdict, tone=tone, rationale=" ".join(parts))


def _highlights(s: StartupDetail, grants: list, patents: list) -> list[str]:
    out = [f"{d.name} readiness at level {d.level}/9: {d.summary}" for d in s.levels if d.level >= 7]
    if s.scores.ocean_areas_covered:
        areas = sorted({k.area_name for k in s.ocean_kpis if k.evidence_level > 0})
        out.append(f"Ocean impact evidence ({s.scores.ocean_evidence_label.lower()}) in {len(areas)} area(s): {', '.join(areas)}.")
    out += [f"{c.name} scores {c.score}/5 on the investment rubric ({'; '.join(c.reasons[:2])})." for c in s.investment.criteria
            if c.score and c.score >= 4 and c.reasons]
    if s.total_disclosed_usd:
        out.append(f"About ${s.total_disclosed_usd / 1e6:.1f}M disclosed funding" + (f", last round {s.last_round_on}." if s.last_round_on else "."))
    if grants:
        eic = sum(g.is_eic for g in grants)
        out.append(f"{len(grants)} EU-funded project(s)" + (f", including {eic} EIC / SME Instrument award(s)." if eic else "."))
    granted = [p for p in patents if p.granted]
    if granted:
        out.append(f"{len(granted)} granted patent(s) of {len(patents)} filed.")
    return out


def _risks(s: StartupDetail, row: sqlite3.Row | None) -> list[str]:
    if not s.assessed:
        return ["Not assessed: readiness, impact and investment scores are unknown."]
    by_code = {d.dimension: d for d in s.levels}
    out = []
    for code in s.scores.lagging_dimensions:
        d = by_code.get(code)
        if d:
            out.append(f"{d.name} lags at level {d.level}/9" + (f"; next milestone: {d.next_summary}" if d.next_summary else "."))
    if s.scores.readiness_spread >= UNBALANCED_SPREAD:
        out.append(f"Unbalanced readiness profile: {s.scores.readiness_spread} levels between the strongest and the weakest dimension.")
    out += [f"{c.name} scores only {c.score}/5 on the investment rubric" + (f" ({'; '.join(c.reasons[:2])})." if c.reasons else ".")
            for c in s.investment.criteria if c.score and c.score <= 2]
    for flag in _json(row["red_flags"] if row else None):
        out.append(flag if isinstance(flag, str) else str(flag.get("flag") or flag.get("reason") or flag))
    if not s.funding_rounds:
        out.append("No funding rounds on record.")
    if s.scores.momentum < 30:
        out.append(f"Weak funding momentum ({s.scores.momentum:.0f}/100).")
    if s.readiness.confidence == "low":
        out.append("Levels rest on public sources only (confidence: low).")
    return out


def _next_steps(s: StartupDetail, row: sqlite3.Row | None) -> list[MemoNextStep]:
    steps = [
        MemoNextStep(action=str(n.get("type") or "Next step"), reason=str(n.get("reason") or ""), resource=n.get("matched_to"))
        for n in _json(row["next_steps"] if row else None) if isinstance(n, dict)
    ]
    if steps:
        return steps
    by_code = {d.dimension: d for d in s.levels}
    steps = [
        MemoNextStep(action=f"Validate {by_code[c].name.lower()} readiness", reason=f"Level {by_code[c].level}/9 is the weakest dimension.",
                     resource=by_code[c].next_summary)
        for c in s.scores.lagging_dimensions if c in by_code
    ]
    steps.append(MemoNextStep(action="First call with the founders", reason="Confirm the evidence behind the scores and the current raise.", resource=None))
    return steps


def _questions(row: sqlite3.Row | None) -> list[str]:
    seen, out = set(), []
    for gap in _json(row["data_gaps"] if row else None):
        q = gap.get("question") if isinstance(gap, dict) else None
        if q and q not in seen:
            seen.add(q)
            out.append(q)
    return out[:MAX_QUESTIONS]


def build_memo(conn: sqlite3.Connection, slug: str) -> InvestmentMemo | None:
    startup = repository.get_startup(conn, slug)
    if startup is None:
        return None
    row = _latest_assessment(conn, slug)
    grants = features_repo.grants(conn, slug) or []
    patents = features_repo.patents(conn, slug) or []
    return InvestmentMemo(
        generated_at=datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M UTC"),
        startup=startup,
        assessment=MemoAssessment(
            engine=row["engine"], assessed_on=row["assessed_at"], confidence=startup.readiness.confidence,
            rationale=row["rationale"], judge_status=row["judge_status"],
        ) if row else None,
        recommendation=_recommendation(startup),
        highlights=_highlights(startup, grants, patents),
        risks=_risks(startup, row),
        questions=_questions(row),
        next_steps=_next_steps(startup, row),
        founders=features_repo.people(conn, slug, founders_only=True) or [],
        investors=features_repo.investors(conn, slug) or [],
        funding=features_repo.funding_events(conn, slug) or [],
        grants=grants,
        patents=patents,
        peers=features_repo.peers(conn, slug, 5) or [],
    )
