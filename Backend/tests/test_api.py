def test_list_sorted_by_potential(client):
    data = client.get("/api/startups").json()
    assert len(data) == 8
    potentials = [s["scores"]["potential"] for s in data]
    assert potentials == sorted(potentials, reverse=True)


def test_filters(client):
    assert {s["slug"] for s in client.get("/api/startups", params={"impact_area": "C"}).json()} == {"seaforester", "kelp-blue"}
    assert all(s["readiness"]["trl"] >= 7 for s in client.get("/api/startups", params={"min_trl": 7}).json())
    assert [s["slug"] for s in client.get("/api/startups", params={"q": "kelp namibia"}).json()] == ["kelp-blue"]


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
