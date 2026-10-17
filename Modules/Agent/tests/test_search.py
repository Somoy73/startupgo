"""Web search in the research pipeline (fake provider, no network)."""

from startup_agent.cache import JsonCache
from startup_agent.errors import AgentError
from startup_agent.search import CachedSearch, SearchHit

from .conftest import RESPONSES, SEARCH_HITS, FakeSearch, build_test_agent
from .helpers import item

SEED_ROUND = item(
    {"date": None, "stage": "seed", "amount": 1_500_000, "currency": "EUR", "investors": ["Blue Fund"]},
    "Acme Ocean closed a EUR 1.5 million seed round led by Blue Fund.",
    "https://news.example/acme-seed",
)


def test_search_adds_independent_pages_that_mention_the_startup(tmp_path):
    search = FakeSearch(SEARCH_HITS)
    agent, fetcher = build_test_agent(tmp_path, searcher=search, responses={**RESPONSES, "G": {"equity_rounds": [SEED_ROUND]}})
    record = agent.profile(name="Acme Ocean", website="https://acme.fi")

    assert search.queries == ['"Acme Ocean" funding']
    assert "https://www.linkedin.com/company/acme" not in fetcher.fetched  # login-walled domains are skipped
    source_urls = {s["url"]: s["source_type"] for s in record.sources}
    assert source_urls["https://news.example/acme-seed"] == "news"
    assert "https://news.example/other" not in source_urls  # fetched, but doesn't mention the startup

    (round_,) = record.facts["equity_rounds"]
    assert round_.status == "verified" and round_.source_url == "https://news.example/acme-seed"
    assert record.facts["stage"].value == "seed"


def test_search_failure_is_recorded_not_fatal(tmp_path):
    class BrokenSearch(FakeSearch):
        def search(self, query, *, limit):
            raise AgentError("quota exceeded")

    agent, _ = build_test_agent(tmp_path, searcher=BrokenSearch([]))
    record = agent.profile(name="Acme Ocean", website="https://acme.fi")
    assert any(e["stage"] == "search" and "quota exceeded" in e["message"] for e in record.errors)
    assert record.facts["dev_stage"].value == "prototype_relevant_env"


def test_cached_search_repeats_no_queries(tmp_path):
    inner = FakeSearch([SearchHit("https://news.example/a", "A")])
    search = CachedSearch(inner, JsonCache(tmp_path))
    assert search.search("q", limit=3) == search.search("q", limit=3) == [SearchHit("https://news.example/a", "A")]
    assert inner.queries == ["q"]
