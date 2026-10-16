-- Startup Go schema
-- Written for SQLite (dev). Kept to portable SQL so it moves to PostgreSQL with
-- minimal changes (INTEGER PRIMARY KEY -> SERIAL/IDENTITY, TEXT dates -> DATE).

PRAGMA foreign_keys = ON;

-- ---------------------------------------------------------------------------
-- Reference data: frameworks
-- ---------------------------------------------------------------------------

-- KTH Innovation Readiness Level dimensions (CRL, TRL, BRL, IPRL, TMRL, FRL)
CREATE TABLE IF NOT EXISTS readiness_dimensions (
    code        TEXT PRIMARY KEY,
    name        TEXT NOT NULL,
    description TEXT NOT NULL,
    sort_order  INTEGER NOT NULL
);

-- One row per (dimension, level 1-9) with the KTH level summary
CREATE TABLE IF NOT EXISTS readiness_levels (
    dimension_code TEXT NOT NULL REFERENCES readiness_dimensions(code),
    level          INTEGER NOT NULL CHECK (level BETWEEN 1 AND 9),
    summary        TEXT NOT NULL,
    PRIMARY KEY (dimension_code, level)
);

-- Ocean Impact Navigator impact areas (A-F)
CREATE TABLE IF NOT EXISTS ocean_impact_areas (
    code        TEXT PRIMARY KEY,
    name        TEXT NOT NULL,
    orientation TEXT NOT NULL
);

-- Ocean Impact Navigator KPIs (30)
CREATE TABLE IF NOT EXISTS ocean_kpis (
    code             TEXT PRIMARY KEY,
    area_code        TEXT NOT NULL REFERENCES ocean_impact_areas(code),
    name             TEXT NOT NULL,
    qualitative_only INTEGER NOT NULL DEFAULT 0
);

-- ---------------------------------------------------------------------------
-- Core entities
-- ---------------------------------------------------------------------------

CREATE TABLE IF NOT EXISTS startups (
    id             INTEGER PRIMARY KEY,
    slug           TEXT NOT NULL UNIQUE,
    name           TEXT NOT NULL,
    tagline        TEXT NOT NULL,
    description    TEXT NOT NULL,
    sector         TEXT NOT NULL,
    country        TEXT NOT NULL,
    city           TEXT,
    founded_year   INTEGER,
    website        TEXT,
    stage          TEXT NOT NULL,   -- pre-seed | seed | series-a | series-b | series-c+ | growth
    pipeline_stage TEXT NOT NULL DEFAULT 'sourced'
        CHECK (pipeline_stage IN ('sourced','screening','diligence','term-sheet','portfolio','passed')),
    created_at     TEXT NOT NULL DEFAULT (datetime('now')),
    updated_at     TEXT NOT NULL DEFAULT (datetime('now'))
);

CREATE TABLE IF NOT EXISTS funding_rounds (
    id              INTEGER PRIMARY KEY,
    startup_id      INTEGER NOT NULL REFERENCES startups(id) ON DELETE CASCADE,
    round_type      TEXT NOT NULL,       -- grant | pre-seed | seed | series-a | ...
    amount          REAL,                -- NULL when undisclosed
    currency        TEXT,                -- ISO 4217 of the announced figure
    announced_on    TEXT,                -- YYYY-MM or YYYY-MM-DD
    lead_investors  TEXT,
    notes           TEXT,
    source_url      TEXT
);

-- A readiness assessment is a dated snapshot; the latest one per startup is "current".
CREATE TABLE IF NOT EXISTS readiness_assessments (
    id          INTEGER PRIMARY KEY,
    startup_id  INTEGER NOT NULL REFERENCES startups(id) ON DELETE CASCADE,
    assessed_on TEXT NOT NULL,
    assessor    TEXT NOT NULL,
    confidence  TEXT NOT NULL CHECK (confidence IN ('low','medium','high')),
    crl  INTEGER NOT NULL CHECK (crl  BETWEEN 1 AND 9),
    trl  INTEGER NOT NULL CHECK (trl  BETWEEN 1 AND 9),
    brl  INTEGER NOT NULL CHECK (brl  BETWEEN 1 AND 9),
    iprl INTEGER NOT NULL CHECK (iprl BETWEEN 1 AND 9),
    tmrl INTEGER NOT NULL CHECK (tmrl BETWEEN 1 AND 9),
    frl  INTEGER NOT NULL CHECK (frl  BETWEEN 1 AND 9),
    rationale TEXT
);

-- Evidence a startup has for each Ocean Impact Navigator KPI.
-- evidence_level: 0 none, 1 claimed, 2 qualitative+evidence, 3 measured, 4 third-party verified
CREATE TABLE IF NOT EXISTS startup_ocean_kpis (
    startup_id     INTEGER NOT NULL REFERENCES startups(id) ON DELETE CASCADE,
    kpi_code       TEXT NOT NULL REFERENCES ocean_kpis(code),
    evidence_level INTEGER NOT NULL CHECK (evidence_level BETWEEN 0 AND 4),
    claim          TEXT NOT NULL,
    source_url     TEXT,
    PRIMARY KEY (startup_id, kpi_code)
);

CREATE TABLE IF NOT EXISTS sources (
    id         INTEGER PRIMARY KEY,
    startup_id INTEGER NOT NULL REFERENCES startups(id) ON DELETE CASCADE,
    title      TEXT NOT NULL,
    url        TEXT NOT NULL
);

CREATE TABLE IF NOT EXISTS notes (
    id         INTEGER PRIMARY KEY,
    startup_id INTEGER NOT NULL REFERENCES startups(id) ON DELETE CASCADE,
    author     TEXT NOT NULL DEFAULT 'analyst',
    body       TEXT NOT NULL,
    created_at TEXT NOT NULL DEFAULT (datetime('now'))
);

CREATE INDEX IF NOT EXISTS idx_rounds_startup      ON funding_rounds(startup_id);
CREATE INDEX IF NOT EXISTS idx_assessments_startup ON readiness_assessments(startup_id, assessed_on);
CREATE INDEX IF NOT EXISTS idx_notes_startup       ON notes(startup_id);
