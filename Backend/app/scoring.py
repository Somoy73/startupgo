"""Startup Go scoring model (v1, rules-based and fully transparent).

Inputs:
  * KTH Innovation Readiness Levels (CRL, TRL, BRL, IPRL, TMRL, FRL), each 1-9
  * Ocean Impact Navigator KPI evidence levels, each 0-4
  * Funding history (stage + recency of last round)

Outputs (all 0-100):
  * readiness       - weighted KTH IRL index
  * ocean_impact    - depth/breadth of evidenced ocean impact
  * momentum        - funding stage and recency
  * potential       - blended Investment Potential

See RESEARCH.md section 2.5: which parts are sourced and which weights are provisional judgment.

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
# Provisional (RESEARCH.md 2.5).
READINESS_WEIGHTS = {"crl": 0.20, "trl": 0.20, "brl": 0.20, "tmrl": 0.15, "frl": 0.15, "iprl": 0.10}

# Provisional (RESEARCH.md 2.5).
POTENTIAL_WEIGHTS = {"readiness": 0.45, "ocean_impact": 0.30, "momentum": 0.25}

# KTH guide: gaps of more than 2-3 levels between dimensions hinder development.
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
DEPTH_KPIS = 3  # how many of the strongest KPIs make up the depth of the ocean score
BREADTH_AREAS = 3  # Navigator areas needed for full breadth
OCEAN_DEPTH_WEIGHT = 0.6
DEFAULT_STAGE_RANK = 2  # unrecognised stage: treated as seed
RECENCY_HORIZON_MONTHS = 48
UNKNOWN_RECENCY = 0.0  # no round date earns no recency credit; momentum_recency_known tells the reader

EVIDENCE_LABELS = {0: "None", 1: "Claimed", 2: "Evidenced", 3: "Measured", 4: "Verified"}

# The agent's Ocean Impact Readiness (1-5, startup_agent.scoring.score_oir) is the canonical impact ladder. Navigator KPI
# evidence is derived from the same facts (startup_agent.navigator): claim/pathway/metrics reach at most KPI level 2,
# a measurement is 3, a third-party-verified measurement is 4. So a KPI cannot be better evidenced than the OIR allows.
OIR_KPI_CAP = {1: 1, 2: 2, 3: 2, 4: 3, 5: 4}

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
    potential: float
    band: str
    readiness_spread: int
    lagging_dimensions: list[str] = field(default_factory=list)
    ocean_evidence_label: str = "None"
    ocean_areas_covered: list[str] = field(default_factory=list)
    ocean_capped_by_oir: bool = False
    ocean_evidence_known: bool = False  # False: no KPI evidence on record, so ocean_impact 0 means "unknown", not "none found to be bad"
    momentum_recency_known: bool = False  # False: no round date, recency counted 0
    potential_coverage: float = 0.0  # share of the potential weights backed by data (1.0 = nothing missing)


def readiness_index(levels: dict[str, int]) -> float:
    """Weighted mean of the six KTH dimensions, rescaled so level 1 = 0 and level 9 = 100."""
    for d in DIMENSIONS:
        if not 1 <= levels[d] <= 9:
            raise ValueError(f"{d} must be 1-9, got {levels[d]}")
    return round(sum(READINESS_WEIGHTS[d] * (levels[d] - 1) / 8 for d in DIMENSIONS) * 100, 1)


def imbalance(levels: dict[str, int]) -> tuple[int, list[str]]:
    values = [levels[d] for d in DIMENSIONS]
    spread = max(values) - min(values)
    mid = median(values)
    lagging = [d.upper() for d in DIMENSIONS if mid - levels[d] >= LAGGING_THRESHOLD]
    return spread, lagging


def cap_kpis(kpis: list[tuple[str, int]], oir_level: int | None) -> tuple[list[tuple[str, int]], bool]:
    """Limit KPI evidence to what the agent's OIR supports; returns the KPIs and whether any were lowered.

    oir_level None means the agent has no impact facts for this startup (e.g. hand-entered KPIs): nothing to check against.
    """
    if oir_level is None:
        return kpis, False
    if oir_level not in OIR_KPI_CAP:
        raise ValueError(f"OIR must be 1-5, got {oir_level}")
    cap = OIR_KPI_CAP[oir_level]
    capped = [(code, min(lvl, cap)) for code, lvl in kpis]
    return capped, capped != kpis


def ocean_impact_score(kpis: list[tuple[str, int]]) -> tuple[float, str, list[str]]:
    """Score ocean impact evidence.

    kpis: (kpi_code, evidence_level) pairs; the area is the first letter of the code.
    Depth (60%) is the mean evidence level of the DEPTH_KPIS strongest KPIs, with missing slots counting 0, so one
    strong KPI is a third of the depth and adding a KPI can never lower the score. Breadth (40%) is the number of
    Navigator impact areas with evidence, up to BREADTH_AREAS.
    """
    for code, lvl in kpis:
        if not 0 <= lvl <= 4:
            raise ValueError(f"{code}: evidence level must be 0-4, got {lvl}")
    addressed = [(code, lvl) for code, lvl in kpis if lvl > 0]
    if not addressed:
        return 0.0, EVIDENCE_LABELS[0], []
    levels = sorted((lvl for _, lvl in addressed), reverse=True)
    areas = sorted({code[0] for code, _ in addressed})
    depth = sum(levels[:DEPTH_KPIS]) / (DEPTH_KPIS * 4)
    breadth = min(len(areas), BREADTH_AREAS) / BREADTH_AREAS
    score = 100 * (OCEAN_DEPTH_WEIGHT * depth + (1 - OCEAN_DEPTH_WEIGHT) * breadth)
    return round(score, 1), EVIDENCE_LABELS[levels[0]], areas


def months_between(earlier: date, later: date) -> int:
    return (later.year - earlier.year) * 12 + (later.month - earlier.month)


def parse_partial_date(value: str | None) -> date | None:
    """Accept YYYY, YYYY-MM or YYYY-MM-DD."""
    if not value:
        return None
    parts = [int(p) for p in value.split("-")]
    year, month, day = (parts + [1, 1])[:3]
    return date(year, month, day)


def stage_rank(stage: str) -> int:
    """Rank of a funding stage; tolerant of case and of the Agent's underscore spelling (pre_seed, series_a)."""
    return STAGE_RANK.get(stage.strip().lower().replace("_", "-"), DEFAULT_STAGE_RANK)


def momentum_score(stage: str, last_round: date | None, today: date | None = None) -> float:
    today = today or date.today()
    stage_part = stage_rank(stage) / 5
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
    oir_level: int | None = None,
) -> ScoreBreakdown:
    """oir_level: the agent's Ocean Impact Readiness for this startup, if known; it caps the KPI evidence (cap_kpis)."""
    readiness = readiness_index(levels)
    kpis, capped = cap_kpis(kpis, oir_level)
    ocean, evidence_label, areas = ocean_impact_score(kpis)
    momentum = momentum_score(stage, last_round, today)
    spread, lagging = imbalance(levels)
    blended = (
        POTENTIAL_WEIGHTS["readiness"] * readiness
        + POTENTIAL_WEIGHTS["ocean_impact"] * ocean
        + POTENTIAL_WEIGHTS["momentum"] * momentum
    )
    potential = round(min(100.0, max(0.0, blended)), 1)
    coverage = (
        POTENTIAL_WEIGHTS["readiness"]
        + POTENTIAL_WEIGHTS["ocean_impact"] * bool(areas)
        + POTENTIAL_WEIGHTS["momentum"] * (0.6 + 0.4 * (last_round is not None))
    )
    return ScoreBreakdown(
        readiness=readiness,
        ocean_impact=ocean,
        momentum=momentum,
        potential=potential,
        band=band_for(potential),
        readiness_spread=spread,
        lagging_dimensions=lagging,
        ocean_evidence_label=evidence_label,
        ocean_areas_covered=areas,
        ocean_capped_by_oir=capped,
        ocean_evidence_known=bool(areas),
        momentum_recency_known=last_round is not None,
        potential_coverage=round(coverage, 2),
    )


def to_usd(amount: float | None, currency: str | None) -> float | None:
    if amount is None or currency is None:
        return None
    rate = FX_TO_USD.get(currency.upper())
    return None if rate is None else amount * rate
