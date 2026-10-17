"""The research pipeline: candidates → workflow (research, judge, evaluation) → entry file + database."""

from pathlib import Path

from scraper.models import StartupLead

from startup_agent.config import AgentSettings
from startup_agent.database import Candidate
from startup_agent.pipeline import ResearchPipeline

from .test_database import make_db, rows

PROMPTS = Path(__file__).resolve().parents[1] / "prompts"


def settings(tmp_path, monkeypatch, discover: str = "") -> AgentSettings:
    monkeypatch.delenv("STARTUPGO_DB", raising=False)
    make_db(tmp_path / "db.sqlite")
    config = tmp_path / "config.toml"
    config.write_text(
        f"""
[search]
provider = "none"
[judge]
check_support = false
[paths]
output_dir = "out"
cache_dir = "cache"
system_prompt = "{PROMPTS / 'system.md'}"
section_prompt = "{PROMPTS / 'section.md'}"
judge_prompt = "{PROMPTS / 'judge.md'}"
[database]
path = "db.sqlite"
[pipeline]
limit = 3
discover = [{discover}]
""",
        encoding="utf-8",
    )
    return AgentSettings.load(config)


def test_research_stores_the_entry_and_the_assessment(tmp_path, monkeypatch, agent):
    s = settings(tmp_path, monkeypatch)
    pipeline = ResearchPipeline(s, build=lambda settings, refresh: agent)
    result = pipeline.research(Candidate("Acme Ocean", "https://acme.fi"))
    assert (result["slug"], result["created"], result["stored"], result["trl"]) == ("acme-ocean", True, True, 6)
    assert result["review_status"].startswith("accepted")
    assert (s.output_dir / "startups" / "acme-fi.json").exists()
    assert rows(s.database, "SELECT entry_id FROM agent_entries")[0][0] == "acme-fi"


def test_candidates_are_pending_database_startups_then_new_discovered_leads(tmp_path, monkeypatch, agent):
    s = settings(tmp_path, monkeypatch, discover='{ source = "wellfound", url = "https://wellfound.com/startups/industry/x" }')
    fake_agent, _ = agent
    leads = [
        StartupLead(name="Notpla again", source="wellfound", source_url="https://wellfound.com/x", website="https://notpla.com"),
        StartupLead(name="Acme Ocean", source="wellfound", source_url="https://wellfound.com/x", website="https://acme.fi", tagline="Port sensors"),
    ]
    monkeypatch.setattr(fake_agent, "discover", lambda **kw: leads)
    pipeline = ResearchPipeline(s, build=lambda settings, refresh: agent)

    found, problems = pipeline.candidates(limit=7)
    assert problems == []
    assert [c.slug for c in found[:6]] == ["notpla", "sofar-ocean", "ocean-rainforest", "seabound", "oceanium", "kelp-blue"]
    assert (found[6].name, found[6].slug, found[6].lead["tagline"]) == ("Acme Ocean", None, "Port sensors")  # notpla.com is known
    assert pipeline.candidates(limit=2)[0][1].slug == "sofar-ocean"
    assert [c.slug for c in pipeline.candidates(slugs=["kelp-blue"])[0]] == ["kelp-blue"]


def test_a_failed_candidate_does_not_stop_the_run(tmp_path, monkeypatch, agent):
    pipeline = ResearchPipeline(settings(tmp_path, monkeypatch), build=lambda settings, refresh: agent)
    results = pipeline.run([Candidate("Nowhere", "https://nowhere.example"), Candidate("Acme Ocean", "https://acme.fi")])
    assert results[0]["stored"] is False and results[0]["error"]
    assert results[1]["stored"] is True


def test_config_file_follows_the_runtime_override(tmp_path, monkeypatch):
    s = settings(tmp_path, monkeypatch)
    monkeypatch.setenv("STARTUPGO_AGENT_CONFIG", str(tmp_path / "config.toml"))
    assert AgentSettings.load().output_dir == s.output_dir


def test_a_discovery_url_makes_discovered_startups_the_only_candidates(tmp_path, monkeypatch, agent):
    fake_agent, _ = agent
    leads = [StartupLead(name=f"Lead {i}", source="wellfound", source_url="https://wellfound.com/x", website=f"https://lead{i}.example")
             for i in range(4)]
    asked = []
    monkeypatch.setattr(fake_agent, "discover", lambda **kw: asked.append(kw) or leads)
    pipeline = ResearchPipeline(settings(tmp_path, monkeypatch), build=lambda settings, refresh: agent)
    source = {"source": "wellfound", "url": "https://wellfound.com/startups/industry/aquaculture", "query": None, "location": "", "limit": 9}
    found, _ = pipeline.candidates(limit=3, sources=[source])
    assert [c.name for c in found] == ["Lead 0", "Lead 1", "Lead 2"]  # no database startups
    assert asked == [source]
