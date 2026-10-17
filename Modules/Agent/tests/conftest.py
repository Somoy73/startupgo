"""Shared fixtures: an agent wired to a fake website, registry, LLM and web search."""

import pytest
from scraper.errors import ScraperError

from startup_agent.agent import StartupAgent
from startup_agent.cache import JsonCache
from startup_agent.crawler import PageLoader
from startup_agent.documents import RobotsPolicy
from startup_agent.extraction import PromptTemplates, SectionExtractor
from startup_agent.registry import PRHRegistry
from startup_agent.search import SearchHit

from .helpers import FakeLLM, item, scalar
from .test_registry import COMPANY

PAGES = {
    "https://acme.fi/": '<title>Acme</title><p>Acme Ocean builds sediment sensors for ports.</p>'
                        '<a href="/technology">Tech</a><a href="/team">Team</a><a href="/secret/plans">x</a>',
    "https://acme.fi/technology": "<title>Technology</title><p>Our sensor prototype was tested in the Port of Turku harbour in 2025.</p>",
    "https://acme.fi/team": "<title>Team</title><p>Maria Virtanen, CEO and co-founder. Jussi Laine, CTO, marine engineer.</p>",
    # Pages only reachable through web search
    "https://news.example/acme-seed": "<title>Acme Ocean raises seed</title><p>Acme Ocean closed a EUR 1.5 million seed round led by Blue Fund.</p>",
    "https://news.example/other": "<title>Other</title><p>An unrelated company raised money.</p>",
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


class FakeSearch:
    name = "fake"

    def __init__(self, hits):
        self.hits = hits
        self.queries = []

    def search(self, query, *, limit):
        self.queries.append(query)
        return self.hits[:limit]


SEARCH_HITS = [
    SearchHit("https://acme.fi/team", "own site, already crawled"),
    SearchHit("https://www.linkedin.com/company/acme", "login wall"),
    SearchHit("https://news.example/other", "does not mention Acme Ocean"),
    SearchHit("https://news.example/acme-seed", "Acme Ocean raises seed"),
]


@pytest.fixture
def agent(tmp_path):
    return build_test_agent(tmp_path)


def build_test_agent(tmp_path, *, searcher=None, responses=None, llm=None):
    fetcher = FakeFetcher()
    cache = JsonCache(tmp_path / "cache")
    agent = StartupAgent(
        fetcher=fetcher,
        extractor=SectionExtractor(llm or FakeLLM(responses or RESPONSES), PROMPTS),
        loader=PageLoader(fetcher.fetch_text, cache=cache, robots=RobotsPolicy(ROBOTS.get, "TestBot"), today="2026-10-17", page_chars=5000),
        registry=PRHRegistry(fetcher.fetch_json, today="2026-10-17"),
        max_pages=5,
        section_chars=10_000,
        searcher=searcher,
        search_queries=['"{name}" funding'] if searcher else (),
        max_search_pages=3,
        today="2026-10-17",
    )
    return agent, fetcher


