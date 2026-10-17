import pytest

from app.main import app
from app.search import SearchResult, get_search_wrapper

NO_LEVELS = {"crl": 0, "trl": 0, "brl": 0, "iprl": 0, "tmrl": 0, "frl": 0}
EMPTY_FILTERS = {
    "stages": [], "sectors": [], "countries": [], "regions": [], "impact_areas": [], "pipeline": [],
    "min_levels": NO_LEVELS, "keywords": [], "any_keywords": [],
}


class FakeWrapper:
    def __init__(self, result: SearchResult):
        self.result, self.calls = result, []

    def search(self, *, query, filters):
        self.calls.append((query, filters))
        return self.result


@pytest.fixture()
def use_wrapper():
    def use(fake):
        app.dependency_overrides[get_search_wrapper] = lambda: fake
        return fake

    yield use
    app.dependency_overrides.pop(get_search_wrapper, None)


def test_search_returns_501_until_the_wrapper_is_connected(client):
    r = client.post("/api/search", json={"query": "kelp in the nordics"})
    assert r.status_code == 501
    assert "isn't connected yet" in r.json()["detail"]


def test_search_passes_the_query_to_the_wrapper(client, use_wrapper):
    startups = client.get("/api/startups", params={"q": "kelp namibia"}).json()
    applied = {**EMPTY_FILTERS, "regions": ["africa"], "any_keywords": ["kelp"]}
    fake = use_wrapper(FakeWrapper(SearchResult(startups=startups, filters=applied, notice="from the fake")))

    body = client.post("/api/search", json={"query": "kelp in africa"}).json()
    assert fake.calls == [("kelp in africa", None)]
    assert body == {"query": "kelp in africa", "filters": applied, "notice": "from the fake", "startups": startups}


def test_search_passes_explicit_filters(client, use_wrapper):
    fake = use_wrapper(FakeWrapper(SearchResult(startups=[])))
    edited = {**EMPTY_FILTERS, "pipeline": ["diligence"], "min_levels": {**NO_LEVELS, "trl": 6}}

    body = client.post("/api/search", json={"filters": edited}).json()
    (query, filters), = fake.calls
    assert query is None
    assert filters.pipeline == ["diligence"] and filters.min_levels.trl == 6
    assert body == {"query": None, "filters": None, "notice": None, "startups": []}


@pytest.mark.parametrize(
    "payload",
    [
        {},
        {"query": ""},
        {"query": "x" * 301},
        {"query": "kelp", "filters": EMPTY_FILTERS},
        {"query": "kelp", "sort": "name"},
        {"filters": {**EMPTY_FILTERS, "regions": ["atlantis"]}},
        {"filters": {**EMPTY_FILTERS, "min_levels": {**NO_LEVELS, "trl": 10}}},
        {"filters": {**EMPTY_FILTERS, "unknown": []}},
    ],
)
def test_search_validates_input(client, use_wrapper, payload):
    use_wrapper(FakeWrapper(SearchResult(startups=[])))
    assert client.post("/api/search", json=payload).status_code == 422
