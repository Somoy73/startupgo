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
    (run,) = rows(s.database, "SELECT * FROM assessments WHERE engine = 'agent'")
    assert run["trl"] == 6 and "agent entry acme-fi" in run["rationale"]


def test_research_logs_what_the_agent_retrieved(tmp_path, monkeypatch, agent):
    s = settings(tmp_path, monkeypatch)
    fake_agent, _ = agent
    fake_agent.loader.log = fake_agent.log  # what factory.build_agent does
    pipeline = ResearchPipeline(s, build=lambda settings, refresh: agent)
    pipeline.research(Candidate("Acme Ocean", "https://acme.fi"))
    (run,) = rows(s.database, "SELECT * FROM agent_runs")
    assert (run["name"], run["status"], run["entry_id"]) == ("Acme Ocean", "ok", "acme-fi")
    pages = rows(s.database, "SELECT * FROM agent_retrievals WHERE run_id = ? ORDER BY seq", run["id"])
    assert pages and pages[0]["url"] == "https://acme.fi/" and pages[0]["kind"] == "page"
    assert any(p["used"] for p in pages)
    assert fake_agent.log.items == []  # drained for the next candidate


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
    assert [c.slug for c in found[:2]] == ["healix", "sammy"]  # without a score
    assert (found[2].name, found[2].slug, found[2].lead["tagline"]) == ("Acme Ocean", None, "Port sensors")  # notpla.com is known
    assert len(found) == 3
    assert [c.slug for c in pipeline.candidates(limit=1)[0]] == ["healix"]
    assert [c.slug for c in pipeline.candidates(slugs=["notpla"])[0]] == ["notpla"]  # scored, but asked for


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


def test_scores_land_in_the_unified_database(tmp_path, monkeypatch, agent):
    """On a copy of DB/startupgo_unified.db: an unscored startup is a candidate, then has the agent's score in the views."""
    import shutil
    import sqlite3

    from .test_database import DB_DIR

    db = tmp_path / "startupgo_unified.db"
    shutil.copyfile(DB_DIR / "startupgo_unified.db", db)
    settings(tmp_path, monkeypatch)  # writes config.toml
    monkeypatch.setenv("STARTUPGO_DB", str(db))  # the copy, in place of config.toml's database
    s = AgentSettings.load(tmp_path / "config.toml")
    pipeline = ResearchPipeline(s, build=lambda settings, refresh: agent)
    pending = pipeline.candidates(limit=50, discover=False)[0]
    assert "healix" in {c.slug for c in pending} and "notpla" not in {c.slug for c in pending}  # notpla has a seed estimate

    result = pipeline.research(Candidate("Healix", "https://acme.fi", slug="healix"))  # the fake agent knows acme.fi's pages
    assert (result["slug"], result["stored"], result["created"]) == ("healix", True, False)
    assert "healix" not in {c.slug for c in pipeline.candidates(limit=50, discover=False)[0]}
    conn = sqlite3.connect(db)
    (trl, assessor) = conn.execute("SELECT r.trl, r.assessor FROM readiness_assessments r JOIN startups s ON s.id = r.startup_id "
                                   "WHERE s.slug = 'healix'").fetchone()
    conn.close()
    assert (trl, assessor) == (6, "StartupGo agent")
