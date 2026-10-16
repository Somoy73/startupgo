"""Scores computed by code from facts: TRL, BRL, Ocean Impact Readiness and 10 investment criteria.

Every score keeps the facts that produced it, so "why BRL 5?" links back to quotes.
The rubrics follow the extraction schema; check them against the official framework
documents before relying on them.
"""

from __future__ import annotations

from collections.abc import Callable
from dataclasses import asdict, dataclass, field
from typing import Any

from .derive import Facts, items, value
from .facts import Fact

STATUS_WEIGHT = {"verified": 1.0, "claimed": 0.6, "inferred": 0.5}


@dataclass(slots=True)
class EvidenceRef:
    field: str
    value: Any
    evidence: str
    source_url: str
    status: str

    @classmethod
    def of(cls, fact: Fact) -> EvidenceRef:
        return cls(fact.field, fact.value, fact.evidence, fact.source_url, fact.status)


@dataclass(slots=True)
class LevelScore:
    level: int | None
    scale: int
    basis: list[str] = field(default_factory=list)
    evidence: list[EvidenceRef] = field(default_factory=list)
    status: str | None = None  # strongest status among the facts that set the level
    confidence: float = 0.0


@dataclass(slots=True)
class CriterionScore:
    name: str
    score: int | None
    confidence: float
    confidence_label: str
    fields_found: int
    fields_total: int
    reasons: list[str]


@dataclass(slots=True)
class Scores:
    trl: LevelScore
    brl: LevelScore
    ocean_impact_readiness: LevelScore
    criteria: list[CriterionScore]
    weights: dict[str, float]
    investment_score: float | None  # weighted 1-5 over known criteria
    investment_percent: float | None  # same on 0-100
    overall_confidence: float

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


# --- Level ladders --------------------------------------------------------------------


@dataclass(slots=True)
class _Rule:
    level: int
    basis: str
    facts: list[Fact]


def _ladder(rules: list[_Rule], scale: int) -> LevelScore:
    """Highest level whose rule matched; evidence and confidence from the facts that set it."""
    if not rules:
        return LevelScore(level=None, scale=scale, basis=["No supporting facts found"])
    top = max(r.level for r in rules)
    winning = [r for r in rules if r.level == top]
    facts = [f for r in winning for f in r.facts]
    best = max(facts, key=lambda f: (STATUS_WEIGHT[f.status], f.confidence), default=None)
    return LevelScore(
        level=top,
        scale=scale,
        basis=[f"{r.basis} → {r.level}" for r in sorted(rules, key=lambda r: -r.level)],
        evidence=[EvidenceRef.of(f) for f in facts],
        status=best.status if best else None,
        confidence=best.confidence if best else 0.0,
    )


DEV_STAGE_TRL = {
    "concept": 1,
    "lab_proof": 3,
    "prototype_lab": 4,
    "prototype_relevant_env": 5,
    "demo_operational_env": 7,
    "qualified_system": 8,
    "commercial_operation": 9,
}


def _has_paying_customers(facts: Facts) -> list[Fact]:
    cv = facts.get("customer_validation")
    evidence = [cv] if isinstance(cv, Fact) and cv.value in ("paying_customers", "recurring_revenue") else []
    return evidence + items(facts, "paying_customers")


def score_trl(facts: Facts) -> LevelScore:
    rules: list[_Rule] = []
    if isinstance(dev := facts.get("dev_stage"), Fact):
        level = DEV_STAGE_TRL[dev.value]
        basis = f"dev_stage = {dev.value}"
        supporting = [dev]
        if dev.value == "concept" and (research := items(facts, "patents") + items(facts, "research_origin")):
            level, basis, supporting = 2, "concept backed by research or patents", [dev, *research]
        if dev.value == "commercial_operation":
            if customers := _has_paying_customers(facts):
                supporting = [dev, *customers]
                basis = "commercial_operation with customers"
            else:
                level, basis = 8, "commercial_operation claimed without customer evidence (capped)"
        rules.append(_Rule(level, basis, supporting))
    if pilots := items(facts, "pilots"):
        rules.append(_Rule(6, f"{len(pilots)} pilot(s) in a relevant environment", pilots))
    if certifications := items(facts, "certifications"):
        rules.append(_Rule(8, "certification or qualification", certifications))
    return _ladder(rules, 9)


CUSTOMER_VALIDATION_BRL = {
    "interviews": 4,
    "letters_of_intent": 5,
    "unpaid_pilot": 5,
    "paid_pilot": 6,
    "paying_customers": 6,
    "recurring_revenue": 8,
}


def score_brl(facts: Facts) -> LevelScore:
    rules: list[_Rule] = []

    def add(level: int, basis: str, *names: str) -> None:
        found = [f for n in names for f in items(facts, n)]
        if found:
            rules.append(_Rule(level, basis, found))

    add(1, "business idea stated", "value_proposition", "solution_summary")
    add(2, "market opportunity and customer described", "ocean_problem", "target_customers", "customer_type")
    add(3, "business model drafted", "business_model")
    cv = facts.get("customer_validation")
    if isinstance(cv, Fact) and cv.value in CUSTOMER_VALIDATION_BRL:
        rules.append(_Rule(CUSTOMER_VALIDATION_BRL[cv.value], f"customer_validation = {cv.value}", [cv]))
    add(6, "named or counted paying customers", "paying_customers")
    trend = facts.get("revenue_trend")
    if isinstance(trend, Fact) and trend.value in ("first_revenue", "growing"):
        level = 7 if trend.value == "growing" else 6
        rules.append(_Rule(level, f"revenue_trend = {trend.value}", [trend]))
    geographies = items(facts, "target_geographies")
    if isinstance(cv, Fact) and cv.value == "recurring_revenue" and geographies and len(geographies[0].value) >= 3:
        rules.append(_Rule(9, "recurring revenue across 3+ markets", [cv, *geographies]))
    return _ladder(rules, 9)


def score_oir(facts: Facts) -> LevelScore:
    rules: list[_Rule] = []
    for level, name, basis in (
        (1, "impact_claim", "impact claimed"),
        (2, "impact_pathway", "impact pathway defined"),
        (3, "impact_metrics_defined", "impact metrics defined"),
        (4, "impact_measured", "impact measured"),
    ):
        if found := items(facts, name):
            rules.append(_Rule(level, basis, found))
    measured, verifier = items(facts, "impact_measured"), items(facts, "impact_verified_by")
    if measured and verifier:
        rules.append(_Rule(5, "impact measured and verified by a third party", [*measured, *verifier]))
    return _ladder(rules, 5)


# --- Investment potential: 10 criteria, each 1-5 ------------------------------------------

DEFAULT_WEIGHTS = {
    "Market": 1.0,
    "Product": 1.0,
    "Team": 1.0,
    "Business model": 1.0,
    "Competition": 1.0,
    "Marketing and distribution": 1.0,
    "Financials": 1.0,
    "Tech": 1.0,
    "Deal dynamics": 1.0,
    "Impact": 1.0,
}


def _clamp(n: int) -> int:
    return max(1, min(5, n))


class _Tally:
    """Accumulates points and the reasons for them."""

    def __init__(self, base: int = 1):
        self.score = base
        self.reasons: list[str] = []

    def add(self, points: int, reason: str) -> None:
        self.score += points
        self.reasons.append(reason)

    def set(self, score: int, reason: str) -> None:
        self.score = score
        self.reasons.append(reason)

    def result(self) -> tuple[int, list[str]]:
        return self.score, self.reasons


def _count(facts: Facts, name: str) -> int:
    """Number of list items, or entries in a list-valued fact."""
    found = items(facts, name)
    if len(found) == 1 and isinstance(found[0].value, list):
        return len(found[0].value)
    return len(found)


def _market(f: Facts) -> tuple[int, list[str]]:
    t = _Tally()
    if items(f, "market_size_claim"):
        t.add(1, "market size cited")
    if _count(f, "target_geographies") >= 2:
        t.add(1, "targets 2+ geographies")
    paying = value(f, "paying_customers") or {}
    customers = max(paying.get("count") or 0, len(paying.get("names") or []))
    if customers:
        t.add(1, f"{customers} paying customer(s)")
    if customers >= 10:
        t.add(1, "10+ paying customers")
    return t.result()


def _product(f: Facts) -> tuple[int, list[str]]:
    by_validation = {"none": 1, "interviews": 2, "letters_of_intent": 3, "unpaid_pilot": 3, "paid_pilot": 4, "paying_customers": 4, "recurring_revenue": 5}
    options = [(1, "value proposition stated")] if items(f, "value_proposition") else []
    if cv := value(f, "customer_validation"):
        options.append((by_validation[cv], f"customer validation: {cv}"))
    if pilots := items(f, "pilots"):
        options.append((3, f"{len(pilots)} pilot(s)"))
    score, reason = max(options)
    return score, [reason]


def _team(f: Facts) -> tuple[int, list[str]]:
    founders = [x.value for x in items(f, "founders")]
    t = _Tally()
    if founders:
        t.add(1, f"{len(founders)} founder(s) named")
    if len(founders) >= 2:
        t.add(1, "multiple founders")
    if any(x.get("technical") for x in founders):
        t.add(1, "technical founder")
    if any(x.get("prior_startup") or (x.get("domain_experience_years") or 0) >= 5 for x in founders):
        t.add(1, "prior startup or 5+ years domain experience")
    if items(f, "advisors_board"):
        t.add(1, "board or advisors")
    if missing := value(f, "key_roles_missing"):
        t.add(-1, f"missing: {', '.join(missing)}")
    return t.result()


def _business_model(f: Facts) -> tuple[int, list[str]]:
    t = _Tally()
    if model := value(f, "business_model"):
        t.add(1, f"model: {model}")
        if model in ("saas", "hardware_plus_service", "licensing"):
            t.add(1, "recurring or scalable model")
    if items(f, "pricing"):
        t.add(1, "pricing stated")
    if types := value(f, "customer_type"):
        t.add(1, f"customers: {', '.join(types)}")
    return t.result()


def _competition(f: Facts) -> tuple[int, list[str]]:
    t = _Tally()
    if n := _count(f, "competitors"):
        t.add(1, f"{n} competitor(s) named")
        if n >= 3:
            t.add(1, "maps the competitive landscape")
    if items(f, "differentiation"):
        t.add(2, "differentiation stated")
    return t.result()


def _distribution(f: Facts) -> tuple[int, list[str]]:
    t = _Tally()
    if n := _count(f, "sales_channels"):
        t.add(min(n, 2), f"{n} sales channel(s)")
    if n := _count(f, "distribution_partners"):
        t.add(2, f"{n} distribution partner(s)")
    return t.result()


def _financials(f: Facts) -> tuple[int, list[str]]:
    by_trend = {"none": 1, "declining": 2, "first_revenue": 2, "flat": 3, "growing": 4}
    t = _Tally()
    if trend := value(f, "revenue_trend"):
        t.set(by_trend[trend], f"revenue {trend}")
    elif (revenue := value(f, "revenue_last_fy")) is not None:
        t.set(3 if revenue >= 1_000_000 else 2 if revenue > 0 else 1, f"revenue {revenue:,.0f} EUR")
    if (profit := value(f, "profit_last_fy")) is not None and profit > 0:
        t.add(1, "profitable")
    return t.result()


def _tech(f: Facts, trl: LevelScore) -> tuple[int, list[str]]:
    patents = items(f, "patents")
    t = _Tally()
    if trl.level is not None:
        t.set((trl.level + 1) // 2, f"TRL {trl.level}")
    elif not patents:
        t.reasons.append("technology described, TRL unknown")
    if patents:
        t.add(1, f"{len(patents)} patent(s)")
    return t.result()


def _deal(f: Facts) -> tuple[int, list[str]]:
    by_stage = {"grant_only": 1, "pre_seed": 2, "seed": 3, "series_a": 4, "series_b_plus": 5}
    t = _Tally()
    if stage := value(f, "stage"):
        t.set(by_stage[stage], f"stage {stage}")
    if (value(f, "current_raise") or {}).get("open"):
        t.add(1, "currently raising")
    return t.result()


Rule = Callable[[Facts], tuple[int, list[str]]]


def score_criteria(facts: Facts, trl: LevelScore, oir: LevelScore) -> list[CriterionScore]:
    criteria: list[tuple[str, tuple[str, ...], Rule]] = [
        ("Market", ("market_size_claim", "target_geographies", "paying_customers"), _market),
        ("Product", ("value_proposition", "customer_validation", "pilots"), _product),
        ("Team", ("founders", "team_size", "key_roles_missing", "advisors_board"), _team),
        ("Business model", ("business_model", "pricing", "customer_type"), _business_model),
        ("Competition", ("competitors", "differentiation"), _competition),
        ("Marketing and distribution", ("sales_channels", "distribution_partners"), _distribution),
        ("Financials", ("revenue_last_fy", "profit_last_fy", "equity_last_fy", "revenue_trend"), _financials),
        ("Tech", ("TRL", "patents", "tech_description"), lambda f: _tech(f, trl)),
        ("Deal dynamics", ("stage", "current_raise", "equity_rounds", "total_raised"), _deal),
        ("Impact", ("OIR",), lambda f: (oir.level or 1, [f"Ocean Impact Readiness {oir.level}"])),
    ]
    scores = {"TRL": trl, "OIR": oir}
    out = []
    for name, fields, rule in criteria:
        weights = [_field_weight(facts, scores, field) for field in fields]
        found = sum(1 for w in weights if w > 0)
        confidence = round(sum(weights) / len(weights), 2)
        score, reasons = rule(facts) if found else (None, ["no facts found"])
        out.append(
            CriterionScore(
                name=name,
                score=_clamp(score) if score is not None else None,
                confidence=confidence,
                confidence_label=confidence_label(confidence),
                fields_found=found,
                fields_total=len(fields),
                reasons=reasons,
            )
        )
    return out


def _field_weight(facts: Facts, scores: dict[str, LevelScore], name: str) -> float:
    """Contribution to confidence: verified 1.0, claimed 0.6, inferred 0.5, missing 0."""
    if name in scores:
        status = scores[name].status
        return STATUS_WEIGHT[status] if scores[name].level is not None and status else 0.0
    found = items(facts, name)
    return max((STATUS_WEIGHT[f.status] for f in found), default=0.0)


def confidence_label(confidence: float) -> str:
    return "high" if confidence >= 0.75 else "medium" if confidence >= 0.4 else "low"


def score_all(facts: Facts, weights: dict[str, float] | None = None) -> Scores:
    weights = {**DEFAULT_WEIGHTS, **(weights or {})}
    trl, brl, oir = score_trl(facts), score_brl(facts), score_oir(facts)
    criteria = score_criteria(facts, trl, oir)
    known = [c for c in criteria if c.score is not None]
    known_weight = sum(weights[c.name] for c in known)
    investment = round(sum(weights[c.name] * c.score for c in known) / known_weight, 2) if known_weight else None
    total_weight = sum(weights[c.name] for c in criteria)
    return Scores(
        trl=trl,
        brl=brl,
        ocean_impact_readiness=oir,
        criteria=criteria,
        weights=weights,
        investment_score=investment,
        investment_percent=round((investment - 1) / 4 * 100, 1) if investment is not None else None,
        overall_confidence=round(sum(weights[c.name] * c.confidence for c in criteria) / total_weight, 2),
    )
