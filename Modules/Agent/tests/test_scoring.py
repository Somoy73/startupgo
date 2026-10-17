from startup_agent.derive import key_roles_missing, stage, total_raised
from startup_agent.scoring import score_all, score_brl, score_oir, score_trl

from .helpers import fact

TODAY = "2026-10-17"


class TestTRL:
    def test_dev_stage_sets_level_and_keeps_evidence(self):
        trl = score_trl({"dev_stage": fact("dev_stage", "prototype_relevant_env")})
        assert trl.level == 5
        assert trl.evidence[0].evidence == "quote for dev_stage"

    def test_pilots_and_certifications_raise_level(self):
        facts = {"dev_stage": fact("dev_stage", "prototype_lab"), "pilots": [fact("pilots", {"partner": "Port"})]}
        assert score_trl(facts).level == 6
        facts["certifications"] = fact("certifications", ["DNV type approval"])
        assert score_trl(facts).level == 8

    def test_commercial_operation_needs_customers(self):
        facts = {"dev_stage": fact("dev_stage", "commercial_operation")}
        assert score_trl(facts).level == 8
        facts["customer_validation"] = fact("customer_validation", "paying_customers")
        assert score_trl(facts).level == 9

    def test_concept_with_research_is_two(self):
        facts = {"dev_stage": fact("dev_stage", "concept"), "research_origin": fact("research_origin", "Aalto spin-out")}
        assert score_trl(facts).level == 2

    def test_unknown_without_facts(self):
        assert score_trl({}).level is None


class TestBRL:
    def test_ladder_takes_highest_supported_level(self):
        facts = {
            "value_proposition": fact("value_proposition", "Cheaper monitoring"),
            "business_model": fact("business_model", "saas"),
            "customer_validation": fact("customer_validation", "letters_of_intent"),
        }
        brl = score_brl(facts)
        assert brl.level == 5
        assert brl.basis[0] == "customer_validation = letters_of_intent → 5"

    def test_growing_revenue_and_scaling(self):
        assert score_brl({"revenue_trend": fact("revenue_trend", "growing")}).level == 7
        facts = {
            "customer_validation": fact("customer_validation", "recurring_revenue"),
            "target_geographies": fact("target_geographies", ["Finland", "Norway", "Chile"]),
        }
        assert score_brl(facts).level == 9


def test_oir_requires_third_party_for_level_five():
    facts = {"impact_claim": fact("impact_claim", "x"), "impact_measured": [fact("impact_measured", {"metric": "kg"})]}
    assert score_oir(facts).level == 4
    facts["impact_verified_by"] = fact("impact_verified_by", "DNV")
    assert score_oir(facts).level == 5


class TestCriteria:
    def test_unknown_criteria_have_no_score_and_zero_confidence(self):
        scores = score_all({})
        assert all(c.score is None and c.confidence == 0 for c in scores.criteria)
        assert scores.investment_score is None

    def test_confidence_reflects_found_and_verified_fields(self):
        facts = {
            "founders": [fact("founders", {"name": "A", "role": "CEO", "technical": False}, status="verified")],
            "team_size": fact("team_size", 6),
        }
        team = next(c for c in score_all(facts).criteria if c.name == "Team")
        assert (team.fields_found, team.fields_total) == (2, 4)
        assert team.confidence == round((1.0 + 0.6) / 4, 2)
        assert team.confidence_label == "medium"  # 0.4 is the medium threshold

    def test_weights_change_the_total(self):
        facts = {"dev_stage": fact("dev_stage", "lab_proof"), "customer_validation": fact("customer_validation", "recurring_revenue")}
        assert score_all(facts).investment_score == 3.5  # Tech 2, Product 5
        assert score_all(facts, {"Tech": 3.0}).investment_score == round((3 * 2 + 5) / 4, 2)


class TestDerived:
    def test_key_roles_missing_unknown_without_founders(self):
        assert key_roles_missing({}, TODAY) is None

    def test_key_roles_missing_from_roles(self):
        founders = [fact("founders", {"role": "CEO"}), fact("founders", {"role": "Lead engineer", "technical": True})]
        assert key_roles_missing({"founders": founders}, TODAY).value == ["commercial lead"]

    def test_total_raised_and_stage(self):
        rounds = [
            fact("equity_rounds", {"stage": "pre_seed", "amount": 500_000, "currency": "EUR"}),
            fact("equity_rounds", {"stage": "seed", "amount": 2_000_000, "currency": "USD"}),
        ]
        facts = {"equity_rounds": rounds}
        assert total_raised(facts, TODAY).value == 500_000 + round(2_000_000 * 0.93)
        assert stage(facts, TODAY).value == "seed"
        assert stage({"grants": [fact("grants", {"funder": "Business Finland"})]}, TODAY).value == "grant_only"
