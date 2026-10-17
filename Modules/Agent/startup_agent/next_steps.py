"""Gaps to next steps: rules on the facts, ordered weakest known dimension first.

"Matched to" describes which kind of opportunity to match. Named opportunities come
from the hand-curated opportunity side (investors, grants, partners) once it exists.
"""

from __future__ import annotations

import re
from dataclasses import asdict, dataclass
from datetime import date
from typing import Any

from .derive import Facts, items, value
from .facts import Fact
from .scoring import Scores
from .spec import FIELDS, FIELDS_BY_NAME

LOW_CONFIDENCE = 0.5
SCORE_INPUTS = {"TRL", "BRL", "OIR"}
_RESEARCH_PARTNER = re.compile(r"universit|institut|research|vtt|syke|aalto|polytechnic|laborator", re.IGNORECASE)


@dataclass(slots=True)
class NextStep:
    type: str
    reason: str
    matched_to: str
    dimension: str

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


@dataclass(slots=True)
class DataGap:
    field: str
    section: str
    reason: str  # "not found" or "low confidence"
    question: str

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


def company_age_years(facts: Facts, today: str) -> int | None:
    founded = value(facts, "founded_date")
    if not founded:
        return None
    return date.fromisoformat(today).year - int(founded[:4])


def data_gaps(facts: Facts) -> list[DataGap]:
    """Fields with a first-call question that are missing or low confidence; score inputs first."""
    gaps = []
    for spec in FIELDS:
        if not spec.question:
            continue
        found: list[Fact] = items(facts, spec.name)
        if not found:
            gaps.append(DataGap(spec.name, spec.section, "not found", spec.question))
        elif max(f.confidence for f in found) < LOW_CONFIDENCE:
            gaps.append(DataGap(spec.name, spec.section, "low confidence", spec.question))
    return sorted(gaps, key=lambda g: not SCORE_INPUTS & set(FIELDS_BY_NAME[g.field].feeds))


def next_steps(facts: Facts, scores: Scores, *, today: str) -> list[NextStep]:
    trl, brl, oir = scores.trl.level, scores.brl.level, scores.ocean_impact_readiness.level
    stage = value(facts, "stage")
    steps: list[NextStep] = []

    if trl is not None and brl is not None and trl >= 5 and brl <= 4:
        segments = ", ".join(value(facts, "target_customers") or []) or "the startup's target segments (unknown)"
        steps.append(NextStep("Commercial validation: get a paid pilot", f"TRL {trl} but BRL {brl}",
                              f"Partners and clients in segments: {segments}", "business"))
    if trl is not None and trl <= 4:
        steps.append(NextStep("R&D funding", f"TRL {trl}", f"Grants whose TRL range covers TRL {trl}", "tech"))
    if not items(facts, "grants") and value(facts, "country") == "Finland" and stage in (None, "pre_seed", "seed"):
        age = company_age_years(facts, today)
        size = value(facts, "employee_range") or "size unknown"
        steps.append(NextStep("First public funding", "Finnish early-stage company with no grants found",
                              f"Business Finland programmes matching company age ({age if age is not None else '?'} years) and size ({size})",
                              "funding"))
    if trl is not None and brl is not None and trl >= 6 and brl >= 5 and stage in ("pre_seed", "seed"):
        sector = value(facts, "blue_sector") or "sector unknown"
        country = value(facts, "country") or "geography unknown"
        steps.append(NextStep("Equity round", f"TRL {trl}, BRL {brl}, stage {stage}",
                              f"Investors whose stage ({stage}), ticket size, sector ({sector}) and geography ({country}) match",
                              "funding"))
    if oir is not None and oir <= 2:
        steps.append(NextStep("Impact measurement", f"Ocean Impact Readiness {oir}",
                              "Research partners for measuring impact; impact frameworks such as the Ocean Impact Navigator",
                              "impact"))
    if missing := value(facts, "key_roles_missing"):
        steps.append(NextStep("Hire or advisor", f"Missing: {', '.join(missing)}",
                              "Accelerator programmes and mentor networks", "team"))
    if items(facts, "research_origin") and not _has_research_partner(facts):
        steps.append(NextStep("Research collaboration", "Research origin but no research partner listed",
                              "Research institutes from related EU projects (CORDIS)", "tech"))
    if gaps := data_gaps(facts):
        steps.append(NextStep("Data gap: ask the startup", f"{len(gaps)} field(s) missing or low confidence",
                              "Questions list for the fund's first call (see data_gaps)", "data"))

    strength = _dimension_strength(scores)

    def order(step: NextStep) -> tuple[int, float]:
        if step.dimension == "data":
            return (2, 0.0)  # the first-call question list always comes last
        known = strength.get(step.dimension)
        return (0, known) if known is not None else (1, 0.0)  # unknown is not weak: after known weak dimensions

    return sorted(steps, key=order)


def _has_research_partner(facts: Facts) -> bool:
    names = [p.value.get("partner") or "" for p in items(facts, "pilots")]
    names += [g.value.get("funder") or "" for g in items(facts, "grants")]
    names += value(facts, "distribution_partners") or []
    return any(_RESEARCH_PARTNER.search(n) for n in names)


def _dimension_strength(scores: Scores) -> dict[str, float | None]:
    """0-1 per dimension, None when unknown."""

    def ratio(level: int | None, scale: int) -> float | None:
        return level / scale if level is not None else None

    criteria = {c.name: c.score for c in scores.criteria}
    return {
        "tech": ratio(scores.trl.level, 9),
        "business": ratio(scores.brl.level, 9),
        "impact": ratio(scores.ocean_impact_readiness.level, 5),
        "team": ratio(criteria["Team"], 5),
        "funding": ratio(criteria["Deal dynamics"], 5),
    }
