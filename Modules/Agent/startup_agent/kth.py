"""The four KTH Innovation Readiness Levels the agent doesn't score itself: CRL, IPRL, TMRL and FRL.

TRL and BRL come from scoring.py. These four are computed by code from the same facts, so the
database gets a full six-dimension assessment (DB/unified.sql assessments). Each rule cites
the KTH level summary it stands for (DB/seed.sql readiness_levels). The levels are calibrated to the
seed estimates: a seed-funded startup lands around FRL 6, a Series A around FRL 7.
"""

from __future__ import annotations

import re

from .derive import Facts, items, value
from .facts import Fact
from .scoring import LevelScore, _ladder, _Rule

# Kind codes B* and C* are granted patents (EP 1234567 B1, FI 123456 B); A* are applications.
_PATENT_NUMBER = re.compile(r"^([A-Z]{2})[\d.,/-]+([A-Z]\d?)?$")

CUSTOMER_VALIDATION_CRL = {
    "interviews": (3, "primary feedback from users or experts"),
    "letters_of_intent": (5, "letters of intent: customers confirm problem-solution fit"),
    "unpaid_pilot": (5, "unpaid pilot: customers confirm problem-solution fit"),
    "paid_pilot": (6, "paid pilot: customer testing confirms value"),
    "paying_customers": (7, "first sales"),
    "recurring_revenue": (8, "recurring sales: initial traction"),
}

STAGE_FRL = {
    "grant_only": (3, "grant funding for initial work"),
    "pre_seed": (4, "pre-seed round closed"),
    "seed": (6, "seed round closed"),
    "series_a": (7, "Series A closed"),
    "series_b_plus": (8, "Series B or later closed"),
}


def score_crl(facts: Facts) -> LevelScore:
    rules: list[_Rule] = []
    if described := [f for n in ("ocean_problem", "target_customers", "customer_type") for f in items(facts, n)]:
        rules.append(_Rule(2, "problem and customers described", described))
    cv = facts.get("customer_validation")
    if isinstance(cv, Fact) and cv.value in CUSTOMER_VALIDATION_CRL:
        level, basis = CUSTOMER_VALIDATION_CRL[cv.value]
        rules.append(_Rule(level, basis, [cv]))
    if pilots := [p for p in items(facts, "pilots") if p.value.get("partner")]:
        rules.append(_Rule(5, f"{len(pilots)} pilot(s) with a named partner", pilots))
    paying = facts.get("paying_customers")
    if isinstance(paying, Fact):
        count = max(paying.value.get("count") or 0, len(paying.value.get("names") or []))
        rules.append(_Rule(8 if count >= 10 else 7, f"{count or 'some'} paying customer(s)", [paying]))
    geographies = items(facts, "target_geographies")
    if isinstance(cv, Fact) and cv.value == "recurring_revenue" and geographies and len(geographies[0].value) >= 3:
        rules.append(_Rule(9, "recurring revenue across 3+ markets", [cv, *geographies]))
    return _ladder(rules, 9)


def score_iprl(facts: Facts) -> LevelScore:
    rules: list[_Rule] = []
    if origin := items(facts, "research_origin"):
        rules.append(_Rule(2, "research spin-out: IP to map", origin))
    patents = items(facts, "patents")
    if patents:
        rules.append(_Rule(5, f"{len(patents)} patent application(s) filed", patents))
    parsed = [(p, _PATENT_NUMBER.match(re.sub(r"\s+", "", (p.value.get("number") or "").upper()))) for p in patents]
    offices = {m.group(1) for _, m in parsed if m}
    if len(offices) >= 2:
        rules.append(_Rule(7, f"filed in {len(offices)} patent offices", [p for p, m in parsed if m]))
    if granted := [p for p, m in parsed if m and (m.group(2) or "")[:1] in ("B", "C")]:
        rules.append(_Rule(8, f"{len(granted)} granted patent(s)", granted))
    return _ladder(rules, 9)


def score_tmrl(facts: Facts) -> LevelScore:
    rules: list[_Rule] = []
    founders = items(facts, "founders")
    if (size := facts.get("team_size")) and isinstance(size, Fact) and size.value >= 3:
        rules.append(_Rule(3, f"team of {size.value}", [size]))
    if len(founders) == 1:
        rules.append(_Rule(2, "single founder named", founders))
    if len(founders) >= 2:
        rules.append(_Rule(4, f"{len(founders)} founders", founders))
        missing = value(facts, "key_roles_missing")
        technical = any(f.value.get("technical") for f in founders)
        if technical and missing is not None and "CEO / business lead" not in missing:
            rules.append(_Rule(5, "founding team covers business and technology", founders))
            if not missing and (advisors := items(facts, "advisors_board")):
                rules.append(_Rule(6, "complementary founding team with advisors", [*founders, *advisors]))
                if isinstance(size, Fact) and size.value >= 10:
                    rules.append(_Rule(7, f"team of {size.value} with board and advisors", [size, *advisors]))
    return _ladder(rules, 9)


def score_frl(facts: Facts) -> LevelScore:
    rules: list[_Rule] = []
    stage = facts.get("stage")
    if isinstance(stage, Fact) and stage.value in STAGE_FRL:
        level, basis = STAGE_FRL[stage.value]
        rules.append(_Rule(level, basis, [stage]))
    if grants := items(facts, "grants"):
        rules.append(_Rule(3, f"{len(grants)} grant(s)", grants))
    raise_ = facts.get("current_raise")
    if isinstance(raise_, Fact) and raise_.value.get("open"):
        rules.append(_Rule(5, "currently raising: pitch tested, funding strategy set", [raise_]))
    return _ladder(rules, 9)


def score_kth(facts: Facts) -> dict[str, LevelScore]:
    """CRL, IPRL, TMRL and FRL (level None when no fact supports any rung)."""
    return {"crl": score_crl(facts), "iprl": score_iprl(facts), "tmrl": score_tmrl(facts), "frl": score_frl(facts)}
