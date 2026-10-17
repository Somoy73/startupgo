"""The pipeline endpoints: search filters, matching graphs and agent research jobs."""

import threading

from startup_search import GraphEdge, GraphNode, SearchUnavailable, Subgraph

from app.db import connect
from app.research import ResearchJobs

from .test_api import FakeSearch, match


class FakeGraphSearch(FakeSearch):
    def __init__(self, graph=None, error=None):
        super().__init__(error=error)
        self.graph = graph
        self.calls = []

    async def startup_graph(self, slug, *, hops, max_nodes):
        self.calls.append(("startup", slug, hops, max_nodes))
        if self.error:
            raise self.error
        return self.graph

    async def thesis_graph(self, thesis, *, hops, max_nodes, seeds):
        self.calls.append(("thesis", thesis, hops, max_nodes, seeds))
        return self.graph


GRAPH = Subgraph(
    seeds=("Seaweed",),
    nodes=(GraphNode("Seaweed", "concept", "Seaweed as a business.", 0, ("startup:notpla", "startup:oceanium")),
           GraphNode("KelpCo", "organization", "", 1, ("entry:kelpco",))),
    edges=(GraphEdge("KelpCo", "Seaweed", "farms", "KelpCo farms seaweed.", 1.0),),
    startups=(match("notpla", None, "Notpla", 1.0, ("Seaweed",)), match("oceanium", None, "Oceanium", 1.0, ("Seaweed",)),
              match(None, "kelpco", "KelpCo", 0.5, ("Seaweed",), {"trl": 4, "brl": 3})),
    truncated=False,
)


def test_search_filters_apply_to_database_startups_and_agent_entries(client):
    client.app.state.search = FakeSearch([
        match("notpla", None, "Notpla", 1.0), match("seabound", None, "Seabound", 0.9), match(None, "kelpco", "KelpCo", 0.5, (), {"trl": 4, "brl": 3}),
    ])
    body = client.post("/api/startups/search", json={"query": "ocean", "filters": {"min_trl": 7}}).json()
    assert [r["slug"] for r in body["results"]] == ["notpla"] and body["entries"] == []
    body = client.post("/api/startups/search", json={"query": "ocean", "filters": {"min_trl": 4}}).json()
    assert [e["entry"] for e in body["entries"]] == ["kelpco"]
    body = client.post("/api/startups/search", json={"query": "ocean", "filters": {"stage": "seed"}}).json()
    assert [r["slug"] for r in body["results"]] == ["seabound"] and body["entries"] == []  # entries have no stage
    assert client.post("/api/startups/search", json={"query": "ocean", "filters": {"impact_area": "Z"}}).status_code == 422


def test_startup_and_thesis_graphs(client):
    search = FakeGraphSearch(GRAPH)
    client.app.state.search = search
    body = client.get("/api/startups/notpla/graph", params={"hops": 2}).json()
    assert search.calls[-1] == ("startup", "notpla", 2, 150)
    assert body["seeds"] == ["Seaweed"] and body["nodes"][0]["startups"] == ["startup:notpla", "startup:oceanium"]
    assert body["edges"][0]["keywords"] == "farms"
    assert [r["slug"] for r in body["results"]] == ["notpla", "oceanium"] and body["entries"][0]["entry"] == "kelpco"
    assert client.get("/api/startups/nope/graph").status_code == 404
    assert client.get("/api/startups/notpla/graph", params={"hops": 4}).status_code == 422

    body = client.post("/api/match/graph", json={"thesis": "seaweed farming", "filters": {"min_trl": 7}}).json()
    assert search.calls[-1] == ("thesis", "seaweed farming", 1, 150, 10)
    assert [r["slug"] for r in body["results"]] == ["notpla"] and body["entries"] == []

    client.app.state.search = FakeGraphSearch(error=SearchUnavailable("notpla has not been processed yet"))
    assert client.get("/api/startups/notpla/graph").status_code == 503


def add_unscored(slug, website):
    """A startup without an assessment (every seed startup has one)."""
    conn = connect()
    conn.execute("INSERT INTO startups (slug, name, tagline, description, sector, country, stage, website) "
                 "VALUES (?, ?, '', '', 'Unknown', 'Unknown', 'unknown', ?)", (slug, slug.title(), website))
    conn.commit()
    conn.close()


def wait_for(client, job_id, status="done"):
    for _ in range(200):
        job = client.get(f"/api/research/{job_id}").json()
        if job["status"] == status:
            return job
        threading.Event().wait(0.01)
    raise AssertionError(f"job {job_id} is {job['status']}")


def test_research_job_runs_the_agent_and_links_the_startup(client):
    calls, release = [], threading.Event()

    def research(candidate, refresh):
        calls.append(candidate)
        release.wait(5)
        return {"slug": candidate.slug or "notpla", "stored": True, "trl": 7}

    add_unscored("bluetide", "https://bluetide.example")
    client.app.state.research = ResearchJobs(research)
    job = client.post("/api/research", json={"slug": "bluetide", "urls": ["https://news.example/bluetide"]})
    assert job.status_code == 202 and job.json()["status"] in ("queued", "running")
    again = client.post("/api/research", json={"name": "Blue Tide", "website": "https://www.bluetide.example/about"}).json()
    assert again["id"] == job.json()["id"]  # one open job per startup, also when found by its domain
    release.set()

    done = wait_for(client, job.json()["id"])
    assert (done["slug"], done["result"]["trl"], done["urls"]) == ("bluetide", 7, ["https://news.example/bluetide"])
    assert (calls[0].name, calls[0].website, calls[0].slug) == ("Bluetide", "https://bluetide.example", "bluetide")
    assert done["refresh"] is False  # never scored: the agent's cache is used

    status = client.get("/api/startups/bluetide/research").json()
    assert status["job"]["id"] == done["id"] and status["has_agent_assessment"] is False  # the fake didn't write an entry

    new = client.post("/api/research", json={"name": "Acme Ocean", "website": "https://acme.fi"}).json()
    assert wait_for(client, new["id"])["slug"] == "notpla"  # the startup the fake reported


def test_startups_with_a_score_are_not_researched(client):
    calls = []
    client.app.state.research = ResearchJobs(lambda candidate, refresh: calls.append(candidate) or {})
    r = client.post("/api/research", json={"slug": "notpla"})
    assert r.status_code == 409 and "GET /api/startups/notpla" in r.json()["detail"]
    r = client.post("/api/research", json={"name": "Notpla", "website": "http://notpla.com"})  # same domain as notpla
    assert r.status_code == 409 and "notpla" in r.json()["detail"]
    assert client.post("/api/research", json={"slug": "seaforester"}).status_code == 409  # scored, even without a website
    assert calls == [] and client.get("/api/startups/notpla/research").json()["job"] is None


def add_agent_assessment(slug, trl, brl, missing):
    """The agent's assessment, which stores dimensions without evidence as 1 and names them in the rationale."""
    conn = connect()
    startup_id = conn.execute("SELECT id FROM startups WHERE slug = ?", (slug,)).fetchone()["id"]
    conn.execute("INSERT INTO readiness_assessments (startup_id, assessed_on, assessor, confidence, crl, trl, brl, iprl, tmrl, frl, rationale) "
                 "VALUES (?, '2026-10-17', 'StartupGo agent', 'low', 1, ?, ?, 1, 1, 1, ?)",
                 (startup_id, trl, brl, f"no evidence for {missing} (stored as 1); judge accepted_with_issues"))
    conn.commit()
    conn.close()


def test_scores_without_trl_or_brl_evidence_are_researched_again_without_the_cache(client):
    runs = []
    client.app.state.research = ResearchJobs(lambda candidate, refresh: runs.append((candidate.slug, refresh)) or {"slug": candidate.slug})
    add_unscored("bluetide", "https://bluetide.example")
    add_agent_assessment("bluetide", 1, 1, "CRL, TRL, BRL, IPRL, TMRL, FRL")
    job = client.post("/api/research", json={"slug": "bluetide"})
    assert job.status_code == 202 and wait_for(client, job.json()["id"])["refresh"] is True
    assert runs == [("bluetide", True)]

    add_unscored("kelpco", "https://kelpco.example")
    add_agent_assessment("kelpco", 6, 1, "BRL, IPRL")
    job = client.post("/api/research", json={"name": "KelpCo", "website": "https://kelpco.example"})  # found by domain
    assert job.status_code == 202 and wait_for(client, job.json()["id"])["refresh"] is True

    add_unscored("reefly", "https://reefly.example")
    add_agent_assessment("reefly", 6, 5, "IPRL, FRL")  # TRL and BRL have evidence: the score stands
    assert client.post("/api/research", json={"slug": "reefly"}).status_code == 409


def set_researched_at(slug, when):
    conn = connect()
    conn.execute("UPDATE startups SET agent_researched_at = datetime('now', ?) WHERE slug = ?", (when, slug))
    conn.commit()
    conn.close()


def test_startups_researched_in_the_last_30_days_are_not_researched_again(client):
    runs = []
    client.app.state.research = ResearchJobs(lambda candidate, refresh: runs.append(candidate.slug) or {"slug": candidate.slug})
    add_unscored("bluetide", "https://bluetide.example")
    add_agent_assessment("bluetide", 1, 1, "CRL, TRL, BRL, IPRL, TMRL, FRL")  # an empty score, but researched recently
    set_researched_at("bluetide", "-3 days")
    r = client.post("/api/research", json={"slug": "bluetide"})
    assert r.status_code == 409 and "30 days" in r.json()["detail"]
    r = client.post("/api/research", json={"name": "Blue Tide", "website": "https://bluetide.example"})  # found by domain
    assert r.status_code == 409
    assert client.get("/api/startups/bluetide/research").json()["researched_at"]

    set_researched_at("bluetide", "-31 days")
    job = client.post("/api/research", json={"slug": "bluetide"})
    assert job.status_code == 202 and wait_for(client, job.json()["id"])["refresh"] is True
    assert runs == ["bluetide"]


def test_old_databases_get_the_research_column_from_their_agent_entries(tmp_path):
    import sqlite3

    from app.db import init_db

    path = tmp_path / "old.db"
    conn = sqlite3.connect(path)
    conn.executescript("""
        CREATE TABLE startups (id INTEGER PRIMARY KEY, slug TEXT NOT NULL UNIQUE, name TEXT NOT NULL, tagline TEXT NOT NULL,
            description TEXT NOT NULL, sector TEXT NOT NULL, country TEXT NOT NULL, city TEXT, founded_year INTEGER, website TEXT,
            stage TEXT NOT NULL, pipeline_stage TEXT NOT NULL DEFAULT 'sourced', created_at TEXT, updated_at TEXT);
        CREATE TABLE agent_entries (startup_id INTEGER PRIMARY KEY, entry_id TEXT NOT NULL, generated_at TEXT NOT NULL,
            stored_at TEXT NOT NULL, assessment_id INTEGER, review_status TEXT, open_issues INTEGER NOT NULL DEFAULT 0,
            investment_score REAL, overall_confidence REAL);
        INSERT INTO startups (id, slug, name, tagline, description, sector, country, stage) VALUES
            (1, 'a', 'A', '', '', 'x', 'FI', 'seed'), (2, 'b', 'B', '', '', 'x', 'FI', 'seed');
        INSERT INTO agent_entries (startup_id, entry_id, generated_at, stored_at) VALUES (1, 'a-fi', '2026-10-01', '2026-10-01 10:00:00');
    """)
    conn.close()
    init_db(path)
    conn = sqlite3.connect(path)
    assert conn.execute("SELECT slug, agent_researched_at FROM startups ORDER BY id").fetchall() == [("a", "2026-10-01 10:00:00"), ("b", None)]
    conn.close()
    init_db(path)  # migrating again changes nothing


def test_research_errors(client):
    def broken(candidate, refresh):
        raise RuntimeError("missing LLM credential: set GEMINI_API_KEY in .env")

    client.app.state.research = ResearchJobs(broken)
    add_unscored("bluetide", "https://bluetide.example")
    job = client.post("/api/research", json={"slug": "bluetide"}).json()
    assert "GEMINI_API_KEY" in wait_for(client, job["id"], "error")["error"]

    assert client.post("/api/research", json={"name": "No website"}).status_code == 422
    assert client.post("/api/research", json={"slug": "nope"}).status_code == 404
    add_unscored("nosite", None)
    r = client.post("/api/research", json={"slug": "nosite"})
    assert r.status_code == 422 and "no website" in r.json()["detail"]
    assert client.get("/api/research/999").status_code == 404


def test_jobs_left_open_by_a_restart_are_marked_as_errors(client):
    conn = connect()
    conn.execute("INSERT INTO agent_jobs (name, website, request, status) VALUES ('X', 'https://x.example', '{}', 'running')")
    conn.commit()
    ResearchJobs().recover(conn)
    (status, error) = conn.execute("SELECT status, error FROM agent_jobs").fetchone()
    conn.close()
    assert status == "error" and "restarted" in error
