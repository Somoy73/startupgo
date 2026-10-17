"""Startup Go API."""

import csv
import io
import sqlite3
from contextlib import asynccontextmanager

from fastapi import Depends, FastAPI, HTTPException, Query, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse, Response
from startup_search import SearchError, SearchUnavailable, StartupSearch

from . import features_repo, repository
from .db import get_conn, init_db
from .schemas import (
    AgentEntryMatch,
    AssessmentCreate,
    FeatureDefinition,
    FilterOptions,
    FundingEvent,
    InvestorLink,
    NaturalLanguageSearchRequest,
    NaturalLanguageSearchResponse,
    Note,
    NoteCreate,
    Peer,
    Person,
    PipelineUpdate,
    ScorePreviewRequest,
    Scores,
    SearchMatch,
    StartupCreate,
    StartupDetail,
    StartupFeatures,
    StartupSummary,
)


@asynccontextmanager
async def lifespan(app: FastAPI):
    init_db()
    app.state.search = StartupSearch()  # LightRAG (Modules/Search); opens on the first search
    yield
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

    summaries = repository.summaries(conn, [m.slug for m in matches if m.slug])
    results, entries = [], []
    for match in matches:
        found = {"relevance": match.relevance, "matched": list(match.matched)}
        if match.slug:
            if summary := summaries.get(match.slug):  # missing if deleted since it was processed
                results.append(SearchMatch(**summary.model_dump(), **found, entry=match.entry))
        elif match.entry:
            scores = {k: match.info.get(k) for k in AgentEntryMatch.SCORES}
            entries.append(AgentEntryMatch(entry=match.entry, name=match.name, website=match.website, **found, **scores))
    return NaturalLanguageSearchResponse(query=body.query, results=results, entries=entries)


@app.post("/api/startups", response_model=StartupDetail, status_code=201)
def create_startup(body: StartupCreate, conn: sqlite3.Connection = Conn):
    return repository.create_startup(conn, body)


@app.get("/api/startups/{slug}", response_model=StartupDetail)
def get_startup(slug: str, conn: sqlite3.Connection = Conn):
    startup = repository.get_startup(conn, slug)
    if startup is None:
        raise HTTPException(404, f"Startup '{slug}' not found")
    return startup


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


# --- Success-prediction features (built by DataAPIs/features.py) ---


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
def startup_rounds(slug: str, include_nominal: bool = False, conn: sqlite3.Connection = Conn):
    """Unified funding timeline: announced rounds, UK SH01 priced allotments, SEC Form D, PDL aggregate."""
    return _found(features_repo.funding_events(conn, slug, include_nominal), slug)


@app.get("/api/startups/{slug}/founders", response_model=list[Person])
def startup_founders(slug: str, founders_only: bool = True, conn: sqlite3.Connection = Conn):
    """Founders/officers with every other company they directed (serial-founder evidence)."""
    return _found(features_repo.people(conn, slug, founders_only), slug)


@app.get("/api/startups/{slug}/investors", response_model=list[InvestorLink])
def startup_investors(slug: str, conn: sqlite3.Connection = Conn):
    return _found(features_repo.investors(conn, slug), slug)


@app.get("/api/startups/{slug}/peers", response_model=list[Peer])
def startup_peers(slug: str, limit: int = Query(5, ge=1, le=50), conn: sqlite3.Connection = Conn):
    return _found(features_repo.peers(conn, slug, limit), slug)
