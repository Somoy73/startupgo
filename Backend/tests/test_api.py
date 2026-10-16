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
