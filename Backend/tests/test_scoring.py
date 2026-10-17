from datetime import date

from app import scoring
from startup_agent.facts import Fact
from startup_agent.scoring import score_all

ALL_FIVES = {d: 5 for d in scoring.DIMENSIONS}


def test_readiness_index_bounds():
    assert scoring.readiness_index({d: 1 for d in scoring.DIMENSIONS}) == 0
    assert scoring.readiness_index({d: 9 for d in scoring.DIMENSIONS}) == 100
    assert scoring.readiness_index(ALL_FIVES) == 50


def test_imbalance_reports_spread_and_lagging_without_penalising():
    levels = {**ALL_FIVES, "trl": 9, "iprl": 1}  # spread 8
    spread, lagging = scoring.imbalance(levels)
    assert spread == 8
    assert lagging == ["IPRL"]
    balanced = scoring.score_startup(ALL_FIVES, [], "Seed", None)
    lopsided = scoring.score_startup({**ALL_FIVES, "trl": 9, "iprl": 1}, [], "Seed", None)
    assert lopsided.potential == round(
        scoring.POTENTIAL_WEIGHTS["readiness"] * lopsided.readiness
        + scoring.POTENTIAL_WEIGHTS["momentum"] * lopsided.momentum,
        1,
    )
    assert balanced.readiness_spread == 0


def test_ocean_impact_zero_without_evidence():
    assert scoring.ocean_impact_score([]) == (0.0, "None", [])
    assert scoring.ocean_impact_score([("B2", 0)])[0] == 0.0


def test_ocean_impact_rewards_evidence_and_breadth():
    narrow, _, _ = scoring.ocean_impact_score([("B2", 2)])
    broad, label, areas = scoring.ocean_impact_score([("B2", 2), ("D1", 2), ("F1", 2)])
    verified, top, _ = scoring.ocean_impact_score([("B2", 4)])
    assert broad > narrow
    assert areas == ["B", "D", "F"]
    assert label == "Evidenced"
    assert top == "Verified" and verified > narrow


def test_momentum_decays_with_age():
    today = date(2026, 10, 1)
    fresh = scoring.momentum_score("seed", date(2026, 9, 1), today)
    stale = scoring.momentum_score("seed", date(2021, 1, 1), today)
    assert fresh > stale
    assert stale == round(100 * 0.6 * 2 / 5, 1)


def test_parse_partial_date():
    assert scoring.parse_partial_date("2024") == date(2024, 1, 1)
    assert scoring.parse_partial_date("2024-09") == date(2024, 9, 1)
    assert scoring.parse_partial_date(None) is None


def test_potential_is_clamped_and_banded():
    s = scoring.score_startup({d: 9 for d in scoring.DIMENSIONS}, [("B2", 4), ("D1", 4), ("C5", 4)], "growth", date(2026, 9, 1), date(2026, 10, 1))
    assert 0 <= s.potential <= 100
    assert s.band == "Strong"


def test_to_usd():
    assert scoring.to_usd(1_000_000, "GBP") == 1_270_000
    assert scoring.to_usd(None, "USD") is None
    assert scoring.to_usd(5, "XYZ") is None


def test_backend_uses_agent_investment_matrix():
    facts = {
        "value_proposition": Fact("value_proposition", "Monitoring", "quote", "https://example.com", "website", "2026-10-17", "claimed", 0.7),
        "customer_validation": Fact("customer_validation", "paying_customers", "quote", "https://example.com", "news", "2026-10-17", "verified", 0.8),
        "dev_stage": Fact("dev_stage", "prototype_relevant_env", "quote", "https://example.com", "website", "2026-10-17", "claimed", 0.7),
    }
    backend = scoring.score_facts(facts)
    agent = score_all(facts)
    assert backend.to_dict() == agent.to_dict()


def test_backend_rehydrates_serialized_agent_entry():
    fact_data = {
        "field": "customer_validation",
        "value": "recurring_revenue",
        "evidence": "quote",
        "source_url": "https://example.com",
        "source_type": "news",
        "retrieved_at": "2026-10-17",
        "status": "verified",
        "confidence": 0.8,
    }
    entry = {"sections": {"D": {"facts": {"customer_validation": fact_data}}}}
    assert scoring.score_entry(entry).brl.level == 8
