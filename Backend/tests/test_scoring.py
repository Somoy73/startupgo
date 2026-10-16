from datetime import date

from app import scoring

ALL_FIVES = {d: 5 for d in scoring.DIMENSIONS}


def test_readiness_index_bounds():
    assert scoring.readiness_index({d: 1 for d in scoring.DIMENSIONS}) == 0
    assert scoring.readiness_index({d: 9 for d in scoring.DIMENSIONS}) == 100
    assert scoring.readiness_index(ALL_FIVES) == 50


def test_imbalance_penalises_spread_beyond_three_levels():
    levels = {**ALL_FIVES, "trl": 9, "iprl": 1}  # spread 8
    spread, lagging, penalty = scoring.imbalance(levels)
    assert spread == 8
    assert lagging == ["IPRL"]
    assert penalty == (8 - 3) * scoring.PENALTY_PER_EXTRA_LEVEL


def test_balanced_profile_has_no_penalty():
    assert scoring.imbalance(ALL_FIVES)[2] == 0


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
