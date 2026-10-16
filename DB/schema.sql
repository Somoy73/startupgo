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

-- ---------------------------------------------------------------------------
-- Ingestion from public APIs (DataAPIs/ingest.py) with per-record provenance
-- ---------------------------------------------------------------------------

-- One row per scraper in DataAPIs (mirrors its registry)
CREATE TABLE IF NOT EXISTS data_sources (
    name        TEXT PRIMARY KEY,
    section     TEXT NOT NULL,
    access      TEXT NOT NULL CHECK (access IN ('free','key','paid')),
    endpoint    TEXT NOT NULL,
    use         TEXT,
    notes       TEXT,
    last_status TEXT,            -- ok | error | skipped | stub | not-run
    last_info   TEXT,
    last_run_at TEXT
);

-- Every API call made by the ingester: what was asked, when, and what came back
CREATE TABLE IF NOT EXISTS raw_fetches (
    id          INTEGER PRIMARY KEY,
    source_name TEXT NOT NULL REFERENCES data_sources(name),
    startup_id  INTEGER REFERENCES startups(id) ON DELETE CASCADE,  -- NULL for non-startup pulls
    params      TEXT NOT NULL,   -- JSON
    status      TEXT NOT NULL CHECK (status IN ('ok','error','skipped')),
    error       TEXT,
    size_bytes  INTEGER,
    payload     TEXT,            -- trimmed JSON response
    fetched_at  TEXT NOT NULL DEFAULT (datetime('now'))
);

-- Identifiers in other systems (LEI, Wikidata QID, YC slug, ...)
CREATE TABLE IF NOT EXISTS startup_external_ids (
    startup_id  INTEGER NOT NULL REFERENCES startups(id) ON DELETE CASCADE,
    id_type     TEXT NOT NULL,   -- lei | wikidata_qid | yc_slug | sec_cik | business_id
    external_id TEXT NOT NULL,
    source_name TEXT NOT NULL REFERENCES data_sources(name),
    url         TEXT,
    details     TEXT,            -- JSON
    match_confidence TEXT NOT NULL CHECK (match_confidence IN ('low','medium','high')),
    fetch_id    INTEGER REFERENCES raw_fetches(id),
    PRIMARY KEY (startup_id, id_type, external_id)
);

-- Evidence items found for a startup: patents, papers, news, launches, repos, web history
CREATE TABLE IF NOT EXISTS startup_signals (
    id          INTEGER PRIMARY KEY,
    startup_id  INTEGER NOT NULL REFERENCES startups(id) ON DELETE CASCADE,
    source_name TEXT NOT NULL REFERENCES data_sources(name),
    signal_type TEXT NOT NULL
        CHECK (signal_type IN ('patent','paper','news','launch','repo','web_history','website','registry','filing','profile','job')),
    title       TEXT NOT NULL,
    url         TEXT,
    observed_on TEXT,            -- when the fact was true (publication / snapshot date)
    value       REAL,            -- e.g. points, stars, citations, snapshot count
    unit        TEXT,
    details     TEXT,            -- JSON
    match_confidence TEXT NOT NULL CHECK (match_confidence IN ('low','medium','high')),
    fetch_id    INTEGER REFERENCES raw_fetches(id),
    fetched_at  TEXT NOT NULL DEFAULT (datetime('now')),
    UNIQUE (startup_id, source_name, signal_type, title, url)
);

-- Candidate values for curated startup fields; never overwrites startups.* automatically
CREATE TABLE IF NOT EXISTS field_suggestions (
    id          INTEGER PRIMARY KEY,
    startup_id  INTEGER NOT NULL REFERENCES startups(id) ON DELETE CASCADE,
    field       TEXT NOT NULL,   -- startups column name, e.g. founded_year
    value       TEXT NOT NULL,
    current_value TEXT,          -- what startups.* held when suggested (NULL = gap)
    source_name TEXT NOT NULL REFERENCES data_sources(name),
    evidence    TEXT,
    match_confidence TEXT NOT NULL CHECK (match_confidence IN ('low','medium','high')),
    status      TEXT NOT NULL DEFAULT 'pending' CHECK (status IN ('pending','accepted','rejected')),
    fetch_id    INTEGER REFERENCES raw_fetches(id),
    UNIQUE (startup_id, field, value, source_name)
);

-- Open calls, grants, publicly funded projects and tenders (not tied to one startup)
CREATE TABLE IF NOT EXISTS funding_opportunities (
    id           INTEGER PRIMARY KEY,
    source_name  TEXT NOT NULL REFERENCES data_sources(name),
    external_ref TEXT NOT NULL,
    kind         TEXT NOT NULL CHECK (kind IN ('grant_call','grant','project','tender')),
    title        TEXT NOT NULL,
    status       TEXT,
    opens_on     TEXT,
    deadline     TEXT,
    amount       REAL,
    currency     TEXT,
    organisation TEXT,
    url          TEXT,
    fetch_id     INTEGER REFERENCES raw_fetches(id),
    UNIQUE (source_name, external_ref)
);

-- Market-sizing time series
CREATE TABLE IF NOT EXISTS market_indicators (
    id             INTEGER PRIMARY KEY,
    source_name    TEXT NOT NULL REFERENCES data_sources(name),
    indicator_code TEXT NOT NULL,
    indicator_name TEXT NOT NULL,
    geo            TEXT NOT NULL,
    period         TEXT NOT NULL,
    value          REAL,
    unit           TEXT,
    fetch_id       INTEGER REFERENCES raw_fetches(id),
    UNIQUE (source_name, indicator_code, geo, period)
);

-- VC assessment data dictionary (DataAPIs/parameters.txt, sections A-U) and how each item can be filled
CREATE TABLE IF NOT EXISTS assessment_parameters (
    id           INTEGER PRIMARY KEY,
    section_code TEXT NOT NULL,
    section_name TEXT NOT NULL,
    item_no      INTEGER NOT NULL,
    name         TEXT NOT NULL,
    description  TEXT,
    priority     TEXT CHECK (priority IN ('P0','P1','P2')),
    coverage     TEXT NOT NULL CHECK (coverage IN ('auto','partial','missing')),
        -- auto: filled from DB/API data; partial: indirect proxy only; missing: needs founder, VC or paid data
    filled_by    TEXT,           -- rule evaluated per startup, e.g. col:website, signal:patent, rounds
    sources      TEXT,           -- APIs that feed it (or could, with a key)
    UNIQUE (section_code, item_no)
);

-- Per-startup fill state for every parameter (rebuilt by the ingester)
CREATE TABLE IF NOT EXISTS startup_parameter_status (
    startup_id   INTEGER NOT NULL REFERENCES startups(id) ON DELETE CASCADE,
    parameter_id INTEGER NOT NULL REFERENCES assessment_parameters(id) ON DELETE CASCADE,
    status       TEXT NOT NULL CHECK (status IN ('filled','proxy','empty','not-collectable')),
    evidence_count INTEGER NOT NULL DEFAULT 0,
    detail       TEXT,
    PRIMARY KEY (startup_id, parameter_id)
);

CREATE INDEX IF NOT EXISTS idx_signals_startup  ON startup_signals(startup_id, signal_type);
CREATE INDEX IF NOT EXISTS idx_fetches_source   ON raw_fetches(source_name, startup_id);
CREATE INDEX IF NOT EXISTS idx_suggest_startup  ON field_suggestions(startup_id, field);

-- Gaps: parameters a startup could have from public data but doesn't yet, plus those needing private data
CREATE VIEW IF NOT EXISTS startup_gaps AS
SELECT s.slug, p.section_code, p.item_no, p.name, p.priority, p.coverage, sps.status, p.sources
FROM startup_parameter_status sps
JOIN startups s ON s.id = sps.startup_id
JOIN assessment_parameters p ON p.id = sps.parameter_id
WHERE sps.status IN ('empty','not-collectable');
