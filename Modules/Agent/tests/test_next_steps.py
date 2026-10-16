from startup_agent.next_steps import data_gaps, next_steps
from startup_agent.scoring import score_all

from .helpers import fact

TODAY = "2026-10-17"


def steps_for(facts):
    return next_steps(facts, score_all(facts), today=TODAY)


def test_tech_ahead_of_business_suggests_paid_pilot_first():
    facts = {
        "dev_stage": fact("dev_stage", "prototype_relevant_env"),
        "business_model": fact("business_model", "saas"),
        "target_customers": fact("target_customers", ["ports"]),
        "impact_claim": fact("impact_claim", "Less dredging"),
        "impact_pathway": fact("impact_pathway", "x"),
        "impact_metrics_defined": fact("impact_metrics_defined", ["m3 sediment"]),
    }
    steps = steps_for(facts)
    assert steps[0].type == "Commercial validation: get a paid pilot"
    assert "ports" in steps[0].matched_to


def test_finnish_early_stage_without_grants_gets_public_funding():
    facts = {"country": fact("country", "Finland"), "founded_date": fact("founded_date", "2023-05-01"), "dev_stage": fact("dev_stage", "lab_proof")}
    types = [s.type for s in steps_for(facts)]
    assert "First public funding" in types and "R&D funding" in types
    funding = next(s for s in steps_for(facts) if s.type == "First public funding")
    assert "3 years" in funding.matched_to


def test_equity_round_and_team_gaps():
    facts = {
        "dev_stage": fact("dev_stage", "demo_operational_env"),
        "customer_validation": fact("customer_validation", "unpaid_pilot"),
        "equity_rounds": [fact("equity_rounds", {"stage": "seed", "amount": None})],
        "stage": fact("stage", "seed", status="inferred"),
        "key_roles_missing": fact("key_roles_missing", ["commercial lead"], status="inferred"),
    }
    types = [s.type for s in steps_for(facts)]
    assert "Equity round" in types and "Hire or advisor" in types


def test_research_origin_without_research_partner():
    facts = {"research_origin": fact("research_origin", "VTT spin-out")}
    assert "Research collaboration" in [s.type for s in steps_for(facts)]
    facts["pilots"] = [fact("pilots", {"partner": "VTT Technical Research Centre"})]
    assert "Research collaboration" not in [s.type for s in steps_for(facts)]


def test_data_gaps_list_score_inputs_first_and_flag_low_confidence():
    gaps = data_gaps({"pricing": fact("pricing", "€99/month", confidence=0.3)})
    assert gaps[0].field in {"dev_stage", "pilots", "founded_date", "revenue_last_fy", "profit_last_fy", "business_model",
                             "customer_validation", "paying_customers", "revenue_trend", "impact_pathway",
                             "impact_metrics_defined", "impact_measured", "impact_verified_by", "patents", "grants", "team_size"}
    pricing = next(g for g in gaps if g.field == "pricing")
    assert pricing.reason == "low confidence"


def test_unknown_dimensions_rank_after_known_weak_ones_and_data_gaps_last():
    facts = {"dev_stage": fact("dev_stage", "prototype_relevant_env"), "value_proposition": fact("value_proposition", "x"),
             "country": fact("country", "Finland")}
    types = [s.type for s in steps_for(facts)]
    # business (BRL 1) is known and weak; funding is unknown, not zero
    assert types.index("Commercial validation: get a paid pilot") < types.index("First public funding")
    assert types[-1] == "Data gap: ask the startup"
