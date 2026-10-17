"""Startup Go scoring model (v1, rules-based and fully transparent).

Inputs:
  * KTH Innovation Readiness Levels (CRL, TRL, BRL, IPRL, TMRL, FRL), each 1-9
  * Ocean Impact Navigator KPI evidence levels, each 0-4
  * Funding history (stage + recency of last round)

Outputs (all 0-100):
  * readiness       - weighted KTH IRL index
  * ocean_impact    - depth/breadth of evidenced ocean impact
  * momentum        - funding stage and recency
  * potential       - blended Investment Potential, minus an imbalance penalty

See RESEARCH.md for the rationale behind each component.

The Investment Score Matrix (10 criteria, 1-5) is not recomputed here: it is the research agent's rubric
(Modules/Agent/startup_agent/scoring.py) with the agent's [weights], through score_facts / score_entry and,
per database startup, startup_agent.database.scores_of.
"""

from dataclasses import dataclass, field
from datetime import date
from statistics import median
from typing import Any

from startup_agent.derive import Facts
from startup_agent.facts import Fact
from startup_agent.scoring import Scores as AgentScores
from startup_agent.scoring import score_all as score_agent_facts

DIMENSIONS = ("crl", "trl", "brl", "iprl", "tmrl", "frl")

# Customer, technology and business model carry the most weight; IP the least,
# since many ocean ventures rely on know-how and permits rather than patents.
READINESS_WEIGHTS = {"crl": 0.20, "trl": 0.20, "brl": 0.20, "tmrl": 0.15, "frl": 0.15, "iprl": 0.10}

POTENTIAL_WEIGHTS = {"readiness": 0.45, "ocean_impact": 0.30, "momentum": 0.25}

# KTH guide: gaps of more than 2-3 levels between dimensions hinder development.
MAX_HEALTHY_SPREAD = 3
PENALTY_PER_EXTRA_LEVEL = 5.0
LAGGING_THRESHOLD = 3  # levels below the median that flag a dimension as lagging

STAGE_RANK = {
    "pre-seed": 1,
    "seed": 2,
    "project-finance": 3,
    "series-a": 3,
    "series-b": 4,
    "series-c+": 5,
    "growth": 5,
}
RECENCY_HORIZON_MONTHS = 48
UNKNOWN_RECENCY = 0.25

EVIDENCE_LABELS = {0: "None", 1: "Claimed", 2: "Evidenced", 3: "Measured", 4: "Verified"}

# Approximate static FX to USD, only used to total disclosed funding.
FX_TO_USD = {"USD": 1.0, "EUR": 1.08, "GBP": 1.27, "NOK": 0.093, "DKK": 0.145}


def investment_weights() -> dict[str, float]:
    """The agent's criterion weights ([weights] in Modules/Agent/config.toml, or $STARTUPGO_AGENT_CONFIG's)."""
    from startup_agent import AgentSettings

    return AgentSettings.load().weights


def score_facts(facts: Facts, weights: dict[str, float] | None = None) -> AgentScores:
    """Run the canonical evidence-backed Investment Score Matrix.

    The research agent owns this rubric. Backend callers should use this function for
    agent records instead of recreating criterion rules from database summary fields.
    """
    return score_agent_facts(facts, weights)


def facts_from_entry(entry: dict[str, Any]) -> Facts:
    """Convert a serialized agent entry into the facts accepted by the canonical scorer."""
    facts: Facts = {}
    for section in entry.get("sections", {}).values():
        for name, raw in section.get("facts", {}).items():
            if raw is None:
                continue
            values = raw if isinstance(raw, list) else [raw]
            parsed = [Fact.from_dict(value) for value in values if isinstance(value, dict)]
            if parsed:
                facts[name] = parsed if isinstance(raw, list) else parsed[0]
    return facts


def score_entry(entry: dict[str, Any], weights: dict[str, float] | None = None) -> AgentScores:
    """Score a serialized, judge-reviewed research entry with the agent rubric."""
    return score_facts(facts_from_entry(entry), weights)


@dataclass
class ScoreBreakdown:
    readiness: float
    ocean_impact: float
    momentum: float
    imbalance_penalty: float
    potential: float
    band: str
    readiness_spread: int
    lagging_dimensions: list[str] = field(default_factory=list)
    ocean_evidence_label: str = "None"
    ocean_areas_covered: list[str] = field(default_factory=list)


def readiness_index(levels: dict[str, int]) -> float:
    """Weighted mean of the six KTH dimensions, rescaled so level 1 = 0 and level 9 = 100."""
    return round(sum(READINESS_WEIGHTS[d] * (levels[d] - 1) / 8 for d in DIMENSIONS) * 100, 1)


def imbalance(levels: dict[str, int]) -> tuple[int, list[str], float]:
    values = [levels[d] for d in DIMENSIONS]
    spread = max(values) - min(values)
    mid = median(values)
    lagging = [d.upper() for d in DIMENSIONS if mid - levels[d] >= LAGGING_THRESHOLD]
    penalty = max(0, spread - MAX_HEALTHY_SPREAD) * PENALTY_PER_EXTRA_LEVEL
    return spread, lagging, penalty


def ocean_impact_score(kpis: list[tuple[str, int]]) -> tuple[float, str, list[str]]:
    """Score ocean impact evidence.

    kpis: (kpi_code, evidence_level) pairs; the area is the first letter of the code.
    Combines the strongest evidence (50%), average evidence across addressed KPIs (30%)
    and breadth across Navigator impact areas, capped at 3 areas (20%).
    """
    addressed = [(code, lvl) for code, lvl in kpis if lvl > 0]
    if not addressed:
        return 0.0, EVIDENCE_LABELS[0], []
    levels = [lvl for _, lvl in addressed]
    areas = sorted({code[0] for code, _ in addressed})
    best = max(levels) / 4
    avg = sum(levels) / len(levels) / 4
    breadth = min(len(areas), 3) / 3
    score = 100 * (0.5 * best + 0.3 * avg + 0.2 * breadth)
    return round(score, 1), EVIDENCE_LABELS[max(levels)], areas


def months_between(earlier: date, later: date) -> int:
    return (later.year - earlier.year) * 12 + (later.month - earlier.month)


def parse_partial_date(value: str | None) -> date | None:
    """Accept YYYY, YYYY-MM or YYYY-MM-DD."""
    if not value:
        return None
    parts = [int(p) for p in value.split("-")]
    year, month, day = (parts + [1, 1])[:3]
    return date(year, month, day)


def momentum_score(stage: str, last_round: date | None, today: date | None = None) -> float:
    today = today or date.today()
    stage_part = STAGE_RANK.get(stage, 2) / 5
    if last_round is None:
        recency = UNKNOWN_RECENCY
    else:
        recency = max(0.0, 1 - months_between(last_round, today) / RECENCY_HORIZON_MONTHS)
    return round(100 * (0.6 * stage_part + 0.4 * recency), 1)


def band_for(potential: float) -> str:
    if potential >= 70:
        return "Strong"
    if potential >= 55:
        return "Promising"
    if potential >= 40:
        return "Watch"
    return "Early"


def score_startup(
    levels: dict[str, int],
    kpis: list[tuple[str, int]],
    stage: str,
    last_round: date | None,
    today: date | None = None,
) -> ScoreBreakdown:
    readiness = readiness_index(levels)
    ocean, evidence_label, areas = ocean_impact_score(kpis)
    momentum = momentum_score(stage, last_round, today)
    spread, lagging, penalty = imbalance(levels)
    blended = (
        POTENTIAL_WEIGHTS["readiness"] * readiness
        + POTENTIAL_WEIGHTS["ocean_impact"] * ocean
        + POTENTIAL_WEIGHTS["momentum"] * momentum
    )
    potential = round(min(100.0, max(0.0, blended - penalty)), 1)
    return ScoreBreakdown(
        readiness=readiness,
        ocean_impact=ocean,
        momentum=momentum,
        imbalance_penalty=penalty,
        potential=potential,
        band=band_for(potential),
        readiness_spread=spread,
        lagging_dimensions=lagging,
        ocean_evidence_label=evidence_label,
        ocean_areas_covered=areas,
    )


def to_usd(amount: float | None, currency: str | None) -> float | None:
    if amount is None or currency is None:
        return None
    rate = FX_TO_USD.get(currency.upper())
    return None if rate is None else amount * rate
