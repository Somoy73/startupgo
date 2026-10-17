"""The scrape agent endpoints: a job per request, with progress, then the agent's result."""

import threading

from app.scrape import ScrapeJobs


def wait_for(client, job_id, status="done"):
    for _ in range(200):
        job = client.get(f"/api/agent-scrape/{job_id}").json()
        if job["status"] == status:
            return job
        threading.Event().wait(0.01)
    raise AssertionError(f"job {job_id} is {job['status']}")


def test_scrape_job_passes_the_sources_to_the_agent_and_keeps_its_progress_and_result(client):
    calls, release = [], threading.Event()

    def scrape(tasks, progress, request):
        calls.append((tasks, request))
        progress("Calls: Reading https://funds.example/calls")
        release.wait(5)
        return {"summary": "One call.", "records": [{"title": "Blue Call"}], "gaps": [], "sources": [], "notices": []}

    client.app.state.scrape = ScrapeJobs(scrape)
    body = {"sources": [
        {"goal": "open blue calls", "urls": ["https://funds.example/calls"], "follow_links": True, "max_pages": 3, "mode": "funding_calls",
         "label": "Calls"},
        {"goal": "ocean startups", "mode": "startups", "label": "Startups"},
    ], "stealth": False, "llm": "gemini"}
    job = client.post("/api/agent-scrape", json=body)
    assert job.status_code == 202 and job.json()["status"] in ("queued", "running")

    for _ in range(200):
        running = client.get(f"/api/agent-scrape/{job.json()['id']}").json()
        if running["progress"]:
            break
        threading.Event().wait(0.01)
    assert running["progress"] == ["Calls: Reading https://funds.example/calls"] and running["result"] is None
    release.set()

    done = wait_for(client, job.json()["id"])
    assert done["result"]["records"] == [{"title": "Blue Call"}]
    assert [s["label"] for s in done["sources"]] == ["Calls", "Startups"] and done["llm"] == "gemini"
    tasks, request = calls[0]
    assert [(t.goal, t.urls, t.follow_links, t.max_pages, t.mode, t.label) for t in tasks] == [
        ("open blue calls", ("https://funds.example/calls",), True, 3, "funding_calls", "Calls"),
        ("ocean startups", (), False, 8, "startups", "Startups")]
    assert (request.stealth, request.llm) == (False, "gemini")


def test_one_source_can_be_given_by_goal_and_urls(client):
    calls = []
    client.app.state.scrape = ScrapeJobs(lambda tasks, progress, request: calls.append(tasks) or {"records": []})
    job = client.post("/api/agent-scrape", json={"goal": "fund news", "urls": ["https://news.example/x"], "mode": "funding_rounds"}).json()
    wait_for(client, job["id"])
    assert [(t.goal, t.urls, t.mode) for t in calls[0]] == [("fund news", ("https://news.example/x",), "funding_rounds")]


def test_a_failing_agent_is_recorded_on_the_job(client):
    def scrape(tasks, progress, request):
        raise RuntimeError("web search is off")

    client.app.state.scrape = ScrapeJobs(scrape)
    job = client.post("/api/agent-scrape", json={"goal": "fund news"}).json()
    failed = wait_for(client, job["id"], "error")
    assert failed["error"] == "web search is off" and failed["result"] is None


def test_requests_and_unknown_jobs_are_validated(client):
    assert client.post("/api/agent-scrape", json={"goal": "x"}).status_code == 422  # too short
    assert client.post("/api/agent-scrape", json={}).status_code == 422  # no source
    assert client.post("/api/agent-scrape", json={"goal": "fund news", "urls": ["not a url"]}).status_code == 422
    assert client.post("/api/agent-scrape", json={"goal": "fund news", "max_pages": 99}).status_code == 422
    assert client.post("/api/agent-scrape", json={"goal": "fund news", "mode": "poems"}).status_code == 422
    assert client.post("/api/agent-scrape", json={"sources": [{"goal": "fund news"}] * 9}).status_code == 422
    assert client.post("/api/agent-scrape", json={"goal": "fund news", "llm": "gpt-9"}).status_code == 422
    assert client.get("/api/agent-scrape/99").status_code == 404


RECORD = {"kind": "startup", "title": "Blue Kelp", "details": "Grows kelp for feed.", "website": "https://bluekelp.example",
          "attributes": [{"name": "country", "value": "Norway"}], "source_url": "https://pipeline.example/list",
          "quote": "Blue Kelp grows kelp for feed", "evidence": "page", "self_reported": False, "group": "BlueInvest pipeline"}


def test_a_scraped_startup_is_added_to_the_database_and_listed_as_sourced(client):
    added = client.post("/api/agent-scrape/startups", json={"record": RECORD})
    assert added.status_code == 201 and added.json() == {"slug": "blue-kelp", "name": "Blue Kelp", "status": "created"}

    profile = client.get("/api/startups/blue-kelp")
    assert profile.status_code == 200 and profile.json()["country"] == "Norway" and profile.json()["pipeline_stage"] == "sourced"
    assert "blue-kelp" in {s["slug"] for s in client.get("/api/startups").json()}

    again = client.post("/api/agent-scrape/startups", json={"record": RECORD})
    assert again.status_code == 200 and again.json()["status"] == "exists"


def test_a_scraped_startup_needs_a_website(client):
    no_site = client.post("/api/agent-scrape/startups", json={"record": {**RECORD, "website": ""}})
    assert no_site.status_code == 422 and "website" in no_site.json()["detail"]
    given = client.post("/api/agent-scrape/startups", json={"record": {**RECORD, "title": "Wave Co", "website": ""}, "website": "waveco.example"})
    assert given.status_code == 201 and given.json()["slug"] == "wave-co"
    assert client.post("/api/agent-scrape/startups", json={"record": RECORD, "website": "not a site"}).status_code == 422


def test_info_lists_both_models_and_the_default(client):
    info = client.get("/api/agent-scrape/info").json()
    models = {m["name"]: m for m in info["models"]}
    assert info["default"] in models and {"nvidia", "gemini"} <= set(models)  # Modules/Agent/config.toml
    assert models["gemini"]["provider"] == "gemini" and models["nvidia"]["provider"] == "openai-compatible"
    assert all(isinstance(m["multimodal"], bool) and isinstance(m["key_set"], bool) for m in models.values())
