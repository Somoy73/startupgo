"""Startup Go API."""

import sqlite3
from contextlib import asynccontextmanager

from fastapi import Depends, FastAPI, HTTPException, Query
from fastapi.middleware.cors import CORSMiddleware

from . import repository
from .db import get_conn, init_db
from .schemas import FilterOptions, Note, NoteCreate, PipelineUpdate, StartupDetail, StartupSummary


@asynccontextmanager
async def lifespan(_: FastAPI):
    init_db()
    yield


app = FastAPI(title="Startup Go API", version="0.1.0", lifespan=lifespan)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:5173", "http://127.0.0.1:5173"],
    allow_methods=["*"],
    allow_headers=["*"],
)

Conn = Depends(get_conn)


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
