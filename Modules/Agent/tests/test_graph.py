"""The LangGraph workflow: research agent → evaluation agent."""

from scraper.models import StartupLead

from startup_agent.errors import AgentError
from startup_agent.graph import build_agent_graph
from startup_agent.record import StartupRecord


def run(agent, **state):
    return build_agent_graph(agent).invoke(state)


def test_both_researches_then_evaluates(agent):
    agent, _ = agent
    result = run(agent, mode="both", name="Acme Ocean", website="https://acme.fi")
    assert len(result["records"]) == 1
    (assessment,) = result["assessments"]
    assert assessment["rank"] == 1 and assessment["name"] == "Acme Ocean"
    assert assessment["trl"] == 6
    assert assessment["next_steps"][0] == "Commercial validation: get a paid pilot"
    assert result["evaluated"][0]["scores"]["trl"]["level"] == 6


def test_research_mode_stops_before_evaluation(agent):
    agent, _ = agent
    result = run(agent, mode="research", name="Acme Ocean", website="https://acme.fi")
    assert result["records"][0]["id"] == "acme-fi"
    assert "assessments" not in result


def test_evaluation_ranks_supplied_entries_and_reports_invalid_ones(agent):
    agent, _ = agent
    full = agent.profile(name="Acme Ocean", website="https://acme.fi")
    sparse = StartupRecord.from_dict(full.to_dict())
    sparse.id, sparse.name = "sparse", "Sparse Co"
    sparse.facts = {k: v for k, v in sparse.facts.items() if k in ("name", "website_domain", "solution_summary")}

    result = run(agent, mode="evaluation", records=[sparse.to_dict(), full.to_dict(), {"name": "Broken"}])
    assert [a["name"] for a in result["assessments"]] == ["Acme Ocean", "Sparse Co"]
    assert result["assessments"][1]["unknown"]  # criteria with no facts are reported, not scored as zero
    assert any("Broken" in e for e in result["errors"])


def test_discovery_researches_leads_with_websites(agent, monkeypatch):
    agent, _ = agent
    leads = [
        StartupLead(name="Acme Ocean", source="wellfound", source_url="https://wellfound.com/startups/industry/x", website="https://acme.fi"),
        StartupLead(name="No Site", source="wellfound", source_url="https://wellfound.com/startups/industry/x"),
    ]
    monkeypatch.setattr(agent, "discover", lambda **_: leads)
    result = run(agent, mode="both", source="wellfound", discover_url="https://wellfound.com/startups/industry/x")
    assert [r["name"] for r in result["records"]] == ["Acme Ocean"]
    assert result["skipped"] == [{"name": "No Site", "reason": "no website to research"}]
    assert result["assessments"][0]["name"] == "Acme Ocean"


def test_research_errors_end_the_run_cleanly(agent, monkeypatch):
    agent, _ = agent

    def fail(**_):
        raise AgentError("discovery failed: blocked")

    monkeypatch.setattr(agent, "discover", fail)
    result = run(agent, mode="both", discover_url="https://wellfound.com/startups/industry/x")
    assert result["errors"] == ["research: discovery failed: blocked"]
    assert result["assessments"] == []
