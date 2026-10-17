def test_memo_of_an_assessed_startup(client):
    r = client.get("/api/startups/notpla/memo")
    assert r.status_code == 200
    m = r.json()
    assert m["startup"]["slug"] == "notpla"
    assert m["recommendation"]["verdict"] in {"Advance to due diligence", "Take a first call", "Monitor", "Pass for now"}
    assert m["highlights"] and m["next_steps"]
    assert m["assessment"]["engine"]


def test_memo_of_an_unassessed_startup_asks_for_research(client):
    pending = next(s for s in client.get("/api/startups").json() if not s["assessed"])
    m = client.get(f"/api/startups/{pending['slug']}/memo").json()
    assert m["recommendation"]["verdict"] == "Research first"
    assert m["assessment"] is None


def test_memo_of_an_unknown_startup(client):
    assert client.get("/api/startups/no-such-startup/memo").status_code == 404
