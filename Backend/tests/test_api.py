from startup_search import SearchError, SearchUnavailable, StartupMatch


def test_list_sorted_by_potential(client):
    data = client.get("/api/startups").json()
    assert len(data) == 8
    potentials = [s["scores"]["potential"] for s in data]
    assert potentials == sorted(potentials, reverse=True)


def test_filters(client):
    assert {s["slug"] for s in client.get("/api/startups", params={"impact_area": "C"}).json()} == {"seaforester", "kelp-blue"}
    assert all(s["readiness"]["trl"] >= 7 for s in client.get("/api/startups", params={"min_trl": 7}).json())
    assert [s["slug"] for s in client.get("/api/startups", params={"q": "kelp namibia"}).json()] == ["kelp-blue"]


class FakeSearch:
    """Stands in for StartupSearch: returns fixed matches, or raises."""

    def __init__(self, matches=(), error=None):
        self.matches = list(matches)
        self.error = error
        self.queries = []

    async def search(self, query):
        self.queries.append(query)
        if self.error:
            raise self.error
        return self.matches

    async def close(self):
        pass


def match(slug, entry, name, relevance, matched=(), info=None):
    documents = tuple(d for d in (slug and f"startup:{slug}", entry and f"entry:{entry}") if d)
    return StartupMatch(slug, entry, name, None, info or {}, relevance, tuple(matched), documents)


def test_natural_language_search_returns_startups_and_agent_entries(client):
    scores = {"trl": 4, "brl": 3, "ocean_impact_readiness": 2, "investment_score": 2.5, "overall_confidence": 0.4}
    search = FakeSearch([
        match("notpla", "notpla-com", "Notpla", 1.0, ("Seaweed", "Packaging")),
        match("deleted-since", None, "Gone", 0.8),  # processed, then removed from the database
        match(None, "kelpco", "KelpCo", 0.5, ("Kelp",), scores),
    ])
    client.app.state.search = search
    body = client.post("/api/startups/search", json={"query": "  seaweed packaging  "}).json()
    assert search.queries == ["seaweed packaging"]
    [notpla] = body["results"]
    assert (notpla["slug"], notpla["relevance"], notpla["matched"], notpla["entry"]) == ("notpla", 1.0, ["Seaweed", "Packaging"], "notpla-com")
    assert notpla["readiness"]["trl"] == 8 and notpla["scores"]["potential"] > 0  # the full database summary
    assert body["entries"] == [{"entry": "kelpco", "name": "KelpCo", "website": None, "relevance": 0.5, "matched": ["Kelp"], **scores}]


def test_natural_language_search_errors(client):
    client.app.state.search = FakeSearch(error=SearchUnavailable("missing NVIDIA credential"))
    r = client.post("/api/startups/search", json={"query": "kelp"})
    assert r.status_code == 503 and "NVIDIA" in r.json()["detail"]

    client.app.state.search = FakeSearch(error=SearchError("search failed: rate limited"))
    assert client.post("/api/startups/search", json={"query": "kelp"}).status_code == 502
    assert client.post("/api/startups/search", json={"query": "   "}).status_code == 422


def test_detail(client):
    d = client.get("/api/startups/notpla").json()
    assert d["name"] == "Notpla"
    assert [l["dimension"] for l in d["levels"]] == ["CRL", "TRL", "BRL", "IPRL", "TMRL", "FRL"]
    assert d["funding_rounds"][0]["amount_usd"] == 20_000_000 * 1.27
    assert client.get("/api/startups/nope").status_code == 404


def test_pipeline_and_notes(client):
    r = client.patch("/api/startups/oceanium/pipeline", json={"pipeline_stage": "screening"})
    assert r.status_code == 200 and r.json()["pipeline_stage"] == "screening"
    assert client.patch("/api/startups/oceanium/pipeline", json={"pipeline_stage": "bogus"}).status_code == 422

    r = client.post("/api/startups/oceanium/notes", json={"body": "Ask about offtake agreements"})
    assert r.status_code == 201
    assert client.get("/api/startups/oceanium").json()["notes"][0]["body"] == "Ask about offtake agreements"


def test_compare_and_frameworks(client):
    assert [s["slug"] for s in client.get("/api/compare", params={"slugs": "notpla,seabound,missing"}).json()] == ["notpla", "seabound"]
    fw = client.get("/api/frameworks").json()
    assert len(fw["readiness_dimensions"]) == 6
    assert sum(len(a["kpis"]) for a in fw["ocean_impact_areas"]) == 30


ASSESSMENT = {
    "crl": 3, "trl": 4, "brl": 3, "iprl": 2, "tmrl": 4, "frl": 3,
    "assessor": "Test analyst",
    "confidence": "medium",
    "rationale": "Intro call",
    "ocean_kpis": [{"kpi_code": "B1", "evidence_level": 3, "claim": "Filters 2 t microplastics / yr", "source_url": None}],
}


def test_add_assessment_replaces_current_levels_and_kpis(client):
    r = client.post("/api/startups/clearbot/assessments", json=ASSESSMENT)
    assert r.status_code == 201
    d = r.json()
    assert d["readiness"]["trl"] == 4 and d["readiness"]["assessor"] == "Test analyst"
    assert [k["kpi_code"] for k in d["ocean_kpis"]] == ["B1"]
    assert client.post("/api/startups/nope/assessments", json=ASSESSMENT).status_code == 404


def test_assessment_validation(client):
    missing_claim = {**ASSESSMENT, "ocean_kpis": [{"kpi_code": "B1", "evidence_level": 2, "claim": " "}]}
    assert client.post("/api/startups/clearbot/assessments", json=missing_claim).status_code == 422
    out_of_range = {**ASSESSMENT, "trl": 10}
    assert client.post("/api/startups/clearbot/assessments", json=out_of_range).status_code == 422
    duplicate = {**ASSESSMENT, "ocean_kpis": ASSESSMENT["ocean_kpis"] * 2}
    assert client.post("/api/startups/clearbot/assessments", json=duplicate).status_code == 422


def test_create_startup(client):
    body = {
        "name": "Notpla",  # clashes with an existing slug
        "tagline": "Test",
        "description": "Test company",
        "sector": "Ocean data",
        "country": "Finland",
        "stage": "pre-seed",
        "funding_round": {"round_type": "pre-seed", "amount": 500000, "currency": "EUR", "announced_on": "2026-06"},
        "assessment": ASSESSMENT,
    }
    r = client.post("/api/startups", json=body)
    assert r.status_code == 201
    d = r.json()
    assert d["slug"] == "notpla-2"
    assert d["pipeline_stage"] == "sourced"
    assert d["total_disclosed_usd"] == 500000 * 1.08
    assert len(client.get("/api/startups").json()) == 9


def test_score_preview_matches_stored_scores(client):
    stored = client.get("/api/startups/seabound").json()
    req = {
        **{k: stored["readiness"][k] for k in ("crl", "trl", "brl", "iprl", "tmrl", "frl")},
        "ocean_kpis": [{"kpi_code": k["kpi_code"], "evidence_level": k["evidence_level"]} for k in stored["ocean_kpis"]],
        "stage": stored["stage"],
        "last_round_on": stored["last_round_on"],
    }
    assert client.post("/api/scoring/preview", json=req).json() == stored["scores"]
