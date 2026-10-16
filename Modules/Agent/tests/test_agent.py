"""End-to-end: fake website + fake registry + fake LLM → schema entry."""

import json

import pytest
from scraper.errors import ScraperError
from scraper.models import StartupLead

from startup_agent.agent import StartupAgent
from startup_agent.cache import JsonCache
from startup_agent.crawler import PageLoader
from startup_agent.documents import RobotsPolicy
from startup_agent.extraction import PromptTemplates, SectionExtractor
from startup_agent.record import StartupRecord, record_json_schema
from startup_agent.registry import PRHRegistry
from startup_agent.store import RecordStore

from .helpers import FakeLLM, item, scalar
from .test_registry import COMPANY

PAGES = {
    "https://acme.fi/": '<title>Acme</title><p>Acme Ocean builds sediment sensors for ports.</p>'
                        '<a href="/technology">Tech</a><a href="/team">Team</a><a href="/secret/plans">x</a>',
    "https://acme.fi/technology": "<title>Technology</title><p>Our sensor prototype was tested in the Port of Turku harbour in 2025.</p>",
    "https://acme.fi/team": "<title>Team</title><p>Maria Virtanen, CEO and co-founder. Jussi Laine, CTO, marine engineer.</p>",
}
ROBOTS = {"https://acme.fi/robots.txt": "User-agent: *\nDisallow: /secret"}
PROMPTS = PromptTemplates("system", "Extract section {section_id}: {section_title} {startup_name} {website} {section_note} {field_guide} {documents}")


class FakeFetcher:
    user_agent = "TestBot"

    def __init__(self):
        self.fetched = []

    def fetch_text(self, url):
        self.fetched.append(url)
        if url not in PAGES:
            raise ScraperError(f"404 {url}")
        return PAGES[url]

    def fetch_json(self, url):
        return {"companies": [COMPANY]}


RESPONSES = {
    "A": {"country": scalar("Finland", "Port of Turku harbour", "https://acme.fi/technology")},
    "B": {"solution_summary": scalar("Sediment sensors for ports", "Acme Ocean builds sediment sensors for ports.")},
    "C": {
        "dev_stage": scalar("prototype_relevant_env", "Our sensor prototype was tested in the Port of Turku harbour in 2025.", "https://acme.fi/technology"),
        "pilots": [item({"partner": "Port of Turku", "environment": "harbour", "year": 2025, "outcome": None},
                        "tested in the Port of Turku harbour in 2025", "https://acme.fi/technology")],
    },
    "F": {"founders": [
        item({"name": "Maria Virtanen", "role": "CEO", "domain_experience_years": None, "technical": False, "prior_startup": None},
             "Maria Virtanen, CEO and co-founder.", "https://acme.fi/team"),
        item({"name": "Jussi Laine", "role": "CTO", "domain_experience_years": None, "technical": True, "prior_startup": None},
             "Jussi Laine, CTO, marine engineer.", "https://acme.fi/team"),
    ]},
    "H": {"competitors": scalar(["Hallucinated Corp"], "We beat Hallucinated Corp on price.")},
}


@pytest.fixture
def agent(tmp_path):
    fetcher = FakeFetcher()
    cache = JsonCache(tmp_path / "cache")
    agent = StartupAgent(
        fetcher=fetcher,
        extractor=SectionExtractor(FakeLLM(RESPONSES), PROMPTS),
        loader=PageLoader(fetcher.fetch_text, cache=cache, robots=RobotsPolicy(ROBOTS.get, "TestBot"), today="2026-10-17", page_chars=5000),
        registry=PRHRegistry(fetcher.fetch_json, today="2026-10-17"),
        max_pages=5,
        section_chars=10_000,
        today="2026-10-17",
    )
    return agent, fetcher


def test_profile_builds_a_scored_entry(agent, tmp_path):
    agent, fetcher = agent
    record = agent.profile(name="Acme Ocean", website="acme.fi")
    assert "https://acme.fi/secret/plans" not in fetcher.fetched  # robots.txt respected
    entry = record.to_dict(weights=None)

    a = entry["sections"]["A"]["facts"]
    assert a["business_id"]["value"] == "2739393-2" and a["business_id"]["status"] == "verified"
    assert a["country"]["source_type"] == "registry"  # registry beats the website claim
    assert a["website_domain"]["value"] == "acme.fi"

    c = entry["sections"]["C"]["facts"]
    assert c["dev_stage"]["status"] == "claimed"
    assert c["patents"] is None
    assert entry["sections"]["F"]["facts"]["key_roles_missing"]["value"] == ["commercial lead"]

    scores = entry["scores"]
    assert scores["trl"]["level"] == 6 and scores["trl"]["evidence"]
    assert any(r["field"] == "competitors" for r in entry["rejected_extractions"])
    assert entry["next_steps"][0]["type"] == "Commercial validation: get a paid pilot"
    assert entry["sections"]["J"]["facts"]["last_changed"]["value"]["C"] == "2026-10-17"


def test_entry_round_trips_and_store_writes_index(agent, tmp_path):
    agent, _ = agent
    store = RecordStore(tmp_path / "out")
    path, entry = store.save(agent.profile(name="Acme Ocean", website="https://acme.fi"), weights={})
    reloaded = StartupRecord.from_dict(json.loads(path.read_text()))
    assert reloaded.to_dict(weights={})["scores"] == entry["scores"]
    index = json.loads((tmp_path / "out" / "index.json").read_text())
    assert index[0]["id"] == "acme-fi" and index[0]["trl"] == 6


def test_cached_pages_are_not_refetched(agent):
    agent, fetcher = agent
    agent.profile(name="Acme Ocean", website="https://acme.fi")
    first = len(fetcher.fetched)
    agent.profile(name="Acme Ocean", website="https://acme.fi")
    assert len(fetcher.fetched) == first


def test_lead_listing_is_a_claimed_seed_document(agent):
    agent, _ = agent
    lead = StartupLead(name="Acme Ocean", source="wellfound", source_url="https://wellfound.com/startups/industry/oceans",
                       tagline="Sensors for ports", website="https://acme.fi", stage="Early Stage")
    record = agent.profile_lead(lead)
    assert record.lead["stage"] == "Early Stage"
    assert any(s["url"] == lead.source_url and s["source_type"] == "website" for s in record.sources)


def test_json_schema_covers_every_section():
    schema = record_json_schema()
    sections = schema["properties"]["sections"]["properties"]
    assert list(sections) == list("ABCDEFGHIJ")
    assert "dev_stage" in sections["C"]["properties"]["facts"]["properties"]


def test_all_sections_failing_is_an_error(agent):
    from startup_agent.errors import AgentError

    agent, _ = agent

    class BrokenLLM:
        model = "broken"

        def complete_json(self, **_):
            raise AgentError("model retired")

    agent.extractor.llm = BrokenLLM()
    with pytest.raises(AgentError, match="model retired"):
        agent.profile(name="Acme Ocean", website="https://acme.fi")
