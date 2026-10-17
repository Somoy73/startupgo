"""Startup Go API."""

import csv
import io
import sqlite3
from contextlib import asynccontextmanager

from fastapi import Depends, FastAPI, HTTPException, Query, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse, Response
from startup_agent import AgentError, Candidate
from startup_agent.database import ENGINE, domain, has_score, researched_at
from startup_search import SearchError, SearchUnavailable, StartupMatch, StartupSearch, Subgraph

from . import features_repo, memo, repository, research, scrape
from .db import get_conn, init_db
from .schemas import (
    AgentAssessment,
    AgentEntryMatch,
    AssessmentCreate,
    BlueInvestProfile,
    EuGrant,
    ExternalPeer,
    FeatureDefinition,
    FilterOptions,
    FundingEvent,
    GraphEdgeOut,
    GraphNodeOut,
    GraphResponse,
    InvestmentMemo,
    InvestorLink,
    NaturalLanguageSearchRequest,
    NaturalLanguageSearchResponse,
    Note,
    NoteCreate,
    Patent,
    Peer,
    Person,
    PipelineUpdate,
    ResearchJob,
    ResearchRequest,
    ScorePreviewRequest,
    ScrapeAgentInfo,
    ScrapedStartup,
    ScrapedStartupAdded,
    ScrapeJob,
    ScrapeRequest,
    Scores,
    SearchFilters,
    SearchMatch,
    StartupCreate,
    StartupDetail,
    StartupFeatures,
    StartupResearch,
    StartupSummary,
    ThesisGraphRequest,
)


@asynccontextmanager
async def lifespan(app: FastAPI):
    init_db()
    app.state.search = StartupSearch()  # LightRAG (Modules/Search); opens on the first search
    app.state.research = research.ResearchJobs()  # agent research jobs (Modules/Agent), one at a time
    app.state.scrape = scrape.ScrapeJobs()  # scrape agent jobs (Modules/Agent), one at a time
    yield
    app.state.research.shutdown()
    app.state.scrape.shutdown()
    await app.state.search.close()


app = FastAPI(title="Startup Go API", version="0.1.0", lifespan=lifespan)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:5173", "http://127.0.0.1:5173"],
    allow_methods=["*"],
    allow_headers=["*"],
)

Conn = Depends(get_conn)


@app.exception_handler(repository.InvalidInput)
def invalid_input(_: Request, exc: repository.InvalidInput) -> JSONResponse:
    return JSONResponse(status_code=422, content={"detail": str(exc)})


@app.get("/api/health")
def health() -> dict:
    return {"status": "ok"}


@app.get("/api/startups", response_model=list[StartupSummary])
def list_startups(
    conn: sqlite3.Connection = Conn,
    q: str | None = None,
    sector: str | None = None,
    country: str | None = None,
    stage: str | None = None,
    pipeline_stage: str | None = None,
    impact_area: str | None = Query(None, pattern="^[A-F]$"),
    min_trl: int | None = Query(None, ge=1, le=9),
    min_brl: int | None = Query(None, ge=1, le=9),
    min_potential: float | None = Query(None, ge=0, le=100),
    sort: str = "potential",
):
    return repository.list_startups(
        conn,
        q=q,
        sector=sector,
        country=country,
        stage=stage,
        pipeline_stage=pipeline_stage,
        impact_area=impact_area,
        min_trl=min_trl,
        min_brl=min_brl,
        min_potential=min_potential,
        sort=sort,
    )


@app.post("/api/startups/search", response_model=NaturalLanguageSearchResponse)
async def natural_language_search(body: NaturalLanguageSearchRequest, request: Request, conn: sqlite3.Connection = Conn):
    """Search startups by what they do (LightRAG over the database and the agent's entries)."""
    try:
        matches = await request.app.state.search.search(body.query)
    except SearchUnavailable as exc:
        raise HTTPException(503, str(exc)) from exc
    except SearchError as exc:
        raise HTTPException(502, str(exc)) from exc

    results, entries = _matches(conn, matches, body.filters)
    return NaturalLanguageSearchResponse(query=body.query, results=results, entries=entries)


def _matches(conn: sqlite3.Connection, matches: list[StartupMatch], filters: SearchFilters) -> tuple[list[SearchMatch], list[AgentEntryMatch]]:
    """Search or graph matches as database summaries and agent-only entries, filtered, in the given order."""
    summaries = repository.summaries(conn, [m.slug for m in matches if m.slug])
    results, entries = [], []
    for match in matches:
        found = {"relevance": match.relevance, "matched": list(match.matched)}
        if match.slug:
            summary = summaries.get(match.slug)  # missing if deleted since it was processed
            if summary and repository.passes(summary, filters):
                results.append(SearchMatch(**summary.model_dump(), **found, entry=match.entry))
        elif match.entry:
            scores = {k: match.info.get(k) for k in AgentEntryMatch.SCORES}
            if repository.entry_passes(scores["trl"], scores["brl"], filters):
                entries.append(AgentEntryMatch(entry=match.entry, name=match.name, website=match.website, **found, **scores))
    return results, entries


# --- Matching: N-hop graphs over the search's knowledge graph ------------------------------------


@app.get("/api/startups/{slug}/graph", response_model=GraphResponse)
async def startup_graph(
    slug: str,
    request: Request,
    hops: int = Query(2, ge=0, le=3),
    max_nodes: int = Query(150, ge=1, le=500),
    conn: sqlite3.Connection = Conn,
):
    """The knowledge graph within ``hops`` of a startup, and the startups it reaches (most shared entities first)."""
    _found(conn.execute("SELECT 1 FROM startups WHERE slug = ?", (slug,)).fetchone(), slug)
    graph = await _graph(request.app.state.search.startup_graph(slug, hops=hops, max_nodes=max_nodes))
    return _graph_response(conn, graph, SearchFilters())


@app.post("/api/match/graph", response_model=GraphResponse)
async def thesis_graph(body: ThesisGraphRequest, request: Request, conn: sqlite3.Connection = Conn):
    """An investor thesis in words: the entities it retrieves, their N-hop neighbourhood and the startups in it."""
    graph = await _graph(request.app.state.search.thesis_graph(body.thesis, hops=body.hops, max_nodes=body.max_nodes, seeds=body.seeds))
    return _graph_response(conn, graph, body.filters)


async def _graph(pending) -> Subgraph:
    try:
        return await pending
    except SearchUnavailable as exc:
        raise HTTPException(503, str(exc)) from exc
    except SearchError as exc:
        raise HTTPException(502, str(exc)) from exc


def _graph_response(conn: sqlite3.Connection, graph: Subgraph, filters: SearchFilters) -> GraphResponse:
    results, entries = _matches(conn, list(graph.startups), filters)
    return GraphResponse(
        seeds=list(graph.seeds),
        nodes=[GraphNodeOut(id=n.id, type=n.type, description=n.description, hop=n.hop, startups=list(n.startups)) for n in graph.nodes],
        edges=[GraphEdgeOut(source=e.source, target=e.target, keywords=e.keywords, description=e.description, weight=e.weight) for e in graph.edges],
        truncated=graph.truncated,
        results=results,
        entries=entries,
    )


# --- Agent research: assess a startup that has no agent assessment yet ----------------------------


@app.post("/api/research", response_model=ResearchJob, status_code=202)
def start_research(body: ResearchRequest, request: Request, conn: sqlite3.Connection = Conn):
    """Queue the agent on a database startup (slug) or a new one (name + website). Poll GET /api/research/{id}.

    Only startups without a usable score in the assessments table are researched: none yet, or one where the agent
    found no evidence for TRL or BRL (researched again, ignoring the agent's cache). Any other score gets 409 (read it
    from GET /api/startups/{slug}). A name + website whose domain is a database startup counts as that startup.
    A startup the agent researched in the last 30 days (the agent's max_age_days) also gets 409, whatever the result.
    """
    slug, name, website = body.slug, body.name, body.website
    if slug:
        row = _found(conn.execute("SELECT id, name, website FROM entities WHERE kind = 'startup' AND slug = ?", (slug,)).fetchone(), slug)
    else:
        own = domain(website)
        row = next((r for r in conn.execute("SELECT id, slug, name, website FROM entities WHERE kind = 'startup' AND website IS NOT NULL")
                    if domain(r["website"]) == own), None)
        slug = row["slug"] if row else None
    startup_id = row["id"] if row else None
    if row and (recent := research.researched_recently(conn, startup_id)):
        ran, days = recent
        raise HTTPException(409, f"{slug} was researched by the agent at {ran} UTC: it is researched again {days} days after that")
    refresh = bool(row and has_score(conn, startup_id))
    if refresh and not research.needs_research(conn, startup_id):
        raise HTTPException(409, f"{slug} already has a score: read it from GET /api/startups/{slug}")
    if row:
        name, website = row["name"], website or row["website"]
        if not website:
            raise repository.InvalidInput(f"{slug} has no website: give one to research it")
    candidate = Candidate(name, website, slug=slug, business_id=body.business_id, extra_urls=tuple(body.urls))
    return request.app.state.research.submit(candidate, startup_id, refresh=refresh)


@app.get("/api/research/{job_id}", response_model=ResearchJob)
def research_job(job_id: int, request: Request):
    job = request.app.state.research.get(job_id)
    if job is None:
        raise HTTPException(404, f"research job {job_id} not found")
    return job


# --- Scrape agent: read any public pages, PDFs and images for a goal ----------------------------------


@app.get("/api/agent-scrape/info", response_model=ScrapeAgentInfo)
def scrape_info():
    return scrape.agent_info()


@app.post("/api/agent-scrape", response_model=ScrapeJob, status_code=202)
def start_scrape(body: ScrapeRequest, request: Request):
    """Queue the scrape agent on up to 8 sources (each a goal, URLs (none: it searches the web) and a focus mode), read in turn
    and merged, with a model from GET /api/agent-scrape/info (none: the default). Poll GET /api/agent-scrape/{id}."""
    if body.llm and body.llm not in {m.name for m in scrape.agent_info().models}:
        raise HTTPException(422, f"unknown model {body.llm!r}: see GET /api/agent-scrape/info")
    return request.app.state.scrape.submit(body)


@app.post("/api/agent-scrape/startups", response_model=ScrapedStartupAdded, status_code=201)
def add_scraped_startup(body: ScrapedStartup, response: Response):
    """Add a startup from a scrape result to the database: a sourced startup without a score (opening it queues the research
    agent), found by website domain first. 201 when created or promoted from a BlueInvest candidate, 200 when it existed;
    either way the record is stored as its evidence. 422 without a website."""
    try:
        added = scrape.add_startup(body)
    except AgentError as exc:
        raise repository.InvalidInput(str(exc)) from exc
    if added.status == "exists":
        response.status_code = 200
    return added


@app.get("/api/agent-scrape/{job_id}", response_model=ScrapeJob)
def scrape_job(job_id: int, request: Request):
    job = request.app.state.scrape.get(job_id)
    if job is None:
        raise HTTPException(404, f"scrape job {job_id} not found")
    return job


@app.get("/api/startups/{slug}/research", response_model=StartupResearch)
def startup_research(slug: str, request: Request, conn: sqlite3.Connection = Conn):
    """Whether the agent has scored the startup (its latest accepted assessment), when it last ran, and the latest job."""
    row = _found(conn.execute("SELECT id FROM entities WHERE kind = 'startup' AND slug = ?", (slug,)).fetchone(), slug)
    scored = conn.execute(
        "SELECT * FROM assessments WHERE entity_id = ? AND engine = ? AND trl IS NOT NULL ORDER BY assessed_at DESC, id DESC LIMIT 1",
        (row["id"], ENGINE),
    ).fetchone()
    agent = AgentAssessment(**{k: scored[k] for k in AgentAssessment.model_fields}) if scored else None
    return StartupResearch(slug=slug, has_agent_assessment=agent is not None, agent=agent, researched_at=researched_at(conn, row["id"]),
                           job=request.app.state.research.latest(row["id"]))


@app.post("/api/startups", response_model=StartupDetail, status_code=201)
def create_startup(body: StartupCreate, conn: sqlite3.Connection = Conn):
    return repository.create_startup(conn, body)


@app.get("/api/startups/{slug}", response_model=StartupDetail)
def get_startup(slug: str, conn: sqlite3.Connection = Conn):
    startup = repository.get_startup(conn, slug)
    if startup is None:
        raise HTTPException(404, f"Startup '{slug}' not found")
    return startup


@app.get("/api/startups/{slug}/memo", response_model=InvestmentMemo)
def investment_memo(slug: str, conn: sqlite3.Connection = Conn):
    """One-click investment memo: scores, evidence, highlights, risks, due-diligence questions and next steps."""
    return _found(memo.build_memo(conn, slug), slug)


@app.patch("/api/startups/{slug}/pipeline", response_model=StartupSummary)
def update_pipeline(slug: str, body: PipelineUpdate, conn: sqlite3.Connection = Conn):
    if not repository.set_pipeline_stage(conn, slug, body.pipeline_stage):
        raise HTTPException(404, f"Startup '{slug}' not found")
    return repository.get_startup(conn, slug)


@app.post("/api/startups/{slug}/assessments", response_model=StartupDetail, status_code=201)
def add_assessment(slug: str, body: AssessmentCreate, conn: sqlite3.Connection = Conn):
    startup = repository.add_assessment(conn, slug, body)
    if startup is None:
        raise HTTPException(404, f"Startup '{slug}' not found")
    return startup


@app.post("/api/scoring/preview", response_model=Scores)
def preview_scores(body: ScorePreviewRequest):
    return repository.preview_scores(body)


@app.post("/api/startups/{slug}/notes", response_model=Note, status_code=201)
def add_note(slug: str, body: NoteCreate, conn: sqlite3.Connection = Conn):
    note = repository.add_note(conn, slug, body.body, body.author)
    if note is None:
        raise HTTPException(404, f"Startup '{slug}' not found")
    return note


@app.get("/api/compare", response_model=list[StartupDetail])
def compare(slugs: str = Query(..., description="Comma-separated slugs, max 3"), conn: sqlite3.Connection = Conn):
    wanted = [s for s in slugs.split(",") if s][:3]
    found = [repository.get_startup(conn, s) for s in wanted]
    return [s for s in found if s is not None]


@app.get("/api/filters", response_model=FilterOptions)
def filters(conn: sqlite3.Connection = Conn):
    return repository.filter_options(conn)


@app.get("/api/frameworks")
def frameworks(conn: sqlite3.Connection = Conn) -> dict:
    return repository.frameworks(conn)


# --- Success-prediction features (built by Modules/DataAPIs/features.py) ---


def _found(value, slug: str):
    if value is None:
        raise HTTPException(404, f"Startup '{slug}' not found")
    return value


@app.get("/api/features/catalog", response_model=list[FeatureDefinition])
def feature_catalog(conn: sqlite3.Connection = Conn):
    return features_repo.catalog(conn)


@app.get("/api/features")
def feature_matrix(
    conn: sqlite3.Connection = Conn,
    as_of: str | None = None,
    format: str = Query("json", pattern="^(json|csv)$"),
):
    """All startups x all features: the model-ready table. Missing values are null (unknown), never 0."""
    names, rows = features_repo.feature_matrix(conn, as_of)
    if format == "csv":
        buf = io.StringIO()
        w = csv.DictWriter(buf, fieldnames=["slug", "name", "as_of", *names])
        w.writeheader()
        w.writerows(rows)
        return Response(buf.getvalue(), media_type="text/csv", headers={"Content-Disposition": "attachment; filename=features.csv"})
    return {"features": names, "rows": rows}


@app.get("/api/startups/{slug}/features", response_model=StartupFeatures)
def startup_features(slug: str, as_of: str | None = None, conn: sqlite3.Connection = Conn):
    return _found(features_repo.startup_features(conn, slug, as_of), slug)


@app.get("/api/startups/{slug}/rounds", response_model=list[FundingEvent])
def startup_rounds(slug: str, conn: sqlite3.Connection = Conn):
    """Funding timeline from every source: announced rounds, UK SH01 priced rounds, SEC Form D, EU grants, PDL aggregate."""
    return _found(features_repo.funding_events(conn, slug), slug)


@app.get("/api/startups/{slug}/founders", response_model=list[Person])
def startup_founders(slug: str, founders_only: bool = True, conn: sqlite3.Connection = Conn):
    """Founders (and current board members) with every other company they directed (serial-founder evidence)."""
    return _found(features_repo.people(conn, slug, founders_only), slug)


@app.get("/api/startups/{slug}/investors", response_model=list[InvestorLink])
def startup_investors(slug: str, conn: sqlite3.Connection = Conn):
    return _found(features_repo.investors(conn, slug), slug)


@app.get("/api/startups/{slug}/peers", response_model=list[Peer])
def startup_peers(slug: str, limit: int = Query(5, ge=1, le=50), conn: sqlite3.Connection = Conn):
    return _found(features_repo.peers(conn, slug, limit), slug)


@app.get("/api/startups/{slug}/grants", response_model=list[EuGrant])
def startup_grants(slug: str, conn: sqlite3.Connection = Conn):
    """EU-funded projects the startup takes part in (CORDIS), with its own EU contribution and role."""
    return _found(features_repo.grants(conn, slug), slug)


@app.get("/api/startups/{slug}/patents", response_model=list[Patent])
def startup_patents(slug: str, conn: sqlite3.Connection = Conn):
    """Patents with legal status and ocean-technology groups."""
    return _found(features_repo.patents(conn, slug), slug)


@app.get("/api/discovery/blueinvest", response_model=list[BlueInvestProfile])
def discovery_blueinvest(
    conn: sqlite3.Connection = Conn,
    q: str | None = None,
    sector: str | None = None,
    min_trl: int | None = Query(None, ge=1, le=9),
    matched_only: bool = False,
    limit: int = Query(50, ge=1, le=500),
    offset: int = Query(0, ge=0),
):
    """EU BlueInvest Project Pipeline (~700 blue-economy SMEs): candidates to source, with TRL and sector."""
    return features_repo.blueinvest(conn, q, sector, min_trl, matched_only, limit, offset)


@app.get("/api/startups/{slug}/peers/blueinvest", response_model=list[ExternalPeer])
def startup_blueinvest_peers(slug: str, limit: int = Query(10, ge=1, le=50), conn: sqlite3.Connection = Conn):
    """Most similar companies in the EU BlueInvest pipeline: the competitor / comparison universe."""
    return _found(features_repo.external_peers(conn, slug, limit), slug)
