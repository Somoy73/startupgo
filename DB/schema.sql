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
-- Ingestion from public APIs (Modules/DataAPIs/ingest.py) with per-record provenance
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

-- VC assessment data dictionary (Modules/DataAPIs/parameters.txt, sections A-U) and how each item can be filled
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
    status       TEXT NOT NULL CHECK (status IN ('filled','proxy','empty','not-collectable','not-applicable')),
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

-- ---------------------------------------------------------------------------
-- Success-prediction features (Modules/DataAPIs/features.py). Parameters follow Potanin et al. 2023
-- (arXiv:2309.15552: rounds, investors, founders, categories) plus ocean deep-tech additions.
-- ---------------------------------------------------------------------------

-- Unified funding timeline from every source: announced rounds, UK SH01 allotments, SEC Form D, PDL, grants
CREATE TABLE IF NOT EXISTS funding_events (
    id                 INTEGER PRIMARY KEY,
    startup_id         INTEGER NOT NULL REFERENCES startups(id) ON DELETE CASCADE,
    event_date         TEXT NOT NULL,
    source_name        TEXT NOT NULL,   -- funding_rounds | uk_sh01 | sec_form_d | people_data_labs
    event_type         TEXT NOT NULL
        CHECK (event_type IN ('announced_round','priced_allotment','nominal_allotment','allotment_unparsed','form_d','aggregate')),
    round_label        TEXT,            -- seed | series-a | grant | ... (announced, or inferred)
    amount             REAL,
    currency           TEXT,
    share_class        TEXT,
    shares_allotted    INTEGER,
    price_per_share    REAL,            -- amount paid per share incl. premium
    total_shares_after INTEGER,         -- from the statement of capital
    implied_post_money REAL,            -- price_per_share x total_shares_after
    investor_count     INTEGER,
    details            TEXT,            -- JSON
    source_url         TEXT,
    match_confidence   TEXT NOT NULL DEFAULT 'high' CHECK (match_confidence IN ('low','medium','high')),
    UNIQUE (startup_id, source_name, event_date, share_class, amount)
);

CREATE TABLE IF NOT EXISTS people (
    id            INTEGER PRIMARY KEY,
    name          TEXT NOT NULL,
    ch_officer_id TEXT UNIQUE,          -- Companies House officer id (appointments link)
    nationality   TEXT,
    country_of_residence TEXT,
    pdl_id        TEXT,                 -- People Data Labs person id (contact details are never stored)
    education     TEXT                  -- JSON: [{"school", "degrees"}] from PDL
);
CREATE UNIQUE INDEX IF NOT EXISTS idx_people_pdl ON people(pdl_id);

CREATE TABLE IF NOT EXISTS startup_people (
    startup_id   INTEGER NOT NULL REFERENCES startups(id) ON DELETE CASCADE,
    person_id    INTEGER NOT NULL REFERENCES people(id) ON DELETE CASCADE,
    role         TEXT NOT NULL,         -- director | secretary | psc | form_d_related_person
    is_founder   INTEGER NOT NULL DEFAULT 0,
    appointed_on TEXT,
    resigned_on  TEXT,
    source_name  TEXT NOT NULL,
    PRIMARY KEY (startup_id, person_id, role)
);

-- Every other company a person has directed: the serial-founder signal and its outcomes
CREATE TABLE IF NOT EXISTS person_ventures (
    person_id      INTEGER NOT NULL REFERENCES people(id) ON DELETE CASCADE,
    company_number TEXT NOT NULL,
    company_name   TEXT NOT NULL,
    company_status TEXT,                -- active | dissolved | liquidation | administration | ...
    role           TEXT,
    appointed_on   TEXT,
    resigned_on    TEXT,
    source_name    TEXT NOT NULL,
    PRIMARY KEY (person_id, company_number, role)
);

CREATE TABLE IF NOT EXISTS investors (
    id         INTEGER PRIMARY KEY,
    name       TEXT NOT NULL UNIQUE,
    kind       TEXT,                    -- vc | climate-vc | ocean-vc | accelerator | corporate | angel-network | foundation | ngo | government | unknown
    tier_score REAL,                    -- 0-1 from Modules/DataAPIs/investor_tiers.json (analyst-curated)
    notes      TEXT
);

CREATE TABLE IF NOT EXISTS startup_investors (
    startup_id  INTEGER NOT NULL REFERENCES startups(id) ON DELETE CASCADE,
    investor_id INTEGER NOT NULL REFERENCES investors(id) ON DELETE CASCADE,
    role        TEXT NOT NULL,          -- lead | participant | shareholder_psc
    first_seen  TEXT,
    rounds      INTEGER NOT NULL DEFAULT 1,  -- rounds this investor appears in (follow-on signal)
    source_name TEXT NOT NULL,
    PRIMARY KEY (startup_id, investor_id, role)
);

-- What each feature means (catalogue served by /api/features/catalog)
CREATE TABLE IF NOT EXISTS feature_definitions (
    name        TEXT PRIMARY KEY,
    feature_group TEXT NOT NULL,        -- rounds | investors | founders | category | momentum | risk | integrity | ocean
    description TEXT NOT NULL,
    unit        TEXT,
    importance  TEXT CHECK (importance IN ('high','medium','low')),
    origin      TEXT NOT NULL,          -- paper | user-list | recommended
    sources     TEXT
);

-- Point-in-time feature store: one value per startup, feature and as-of date
CREATE TABLE IF NOT EXISTS startup_features (
    startup_id INTEGER NOT NULL REFERENCES startups(id) ON DELETE CASCADE,
    feature    TEXT NOT NULL REFERENCES feature_definitions(name),
    as_of      TEXT NOT NULL,
    value_num  REAL,
    value_text TEXT,
    evidence   TEXT,                    -- JSON: what it was computed from
    PRIMARY KEY (startup_id, feature, as_of)
);

CREATE TABLE IF NOT EXISTS startup_peers (
    startup_id  INTEGER NOT NULL REFERENCES startups(id) ON DELETE CASCADE,
    peer_id     INTEGER NOT NULL REFERENCES startups(id) ON DELETE CASCADE,
    similarity  REAL NOT NULL,
    shared_tags TEXT,                   -- JSON list
    PRIMARY KEY (startup_id, peer_id)
);

CREATE INDEX IF NOT EXISTS idx_events_startup   ON funding_events(startup_id, event_date);
CREATE INDEX IF NOT EXISTS idx_features_startup ON startup_features(startup_id, as_of);

-- ---------------------------------------------------------------------------
-- EU and ocean-specific sources (Modules/DataAPIs/ingest_eu.py)
-- ---------------------------------------------------------------------------

-- One row per startup participation in an EU-funded project (CORDIS)
CREATE TABLE IF NOT EXISTS eu_grants (
    startup_id        INTEGER NOT NULL REFERENCES startups(id) ON DELETE CASCADE,
    project_id        TEXT NOT NULL,      -- CORDIS project id (grant agreement number)
    acronym           TEXT,
    title             TEXT,
    framework         TEXT,               -- FP7 | H2020 | HORIZON
    topic_codes       TEXT,               -- JSON list, e.g. ["SMEInst-11-2016-2017"]
    legal_basis       TEXT,               -- JSON list, e.g. ["H2020-EU.2.3.1."]
    role              TEXT NOT NULL,      -- coordinator | participant | associatedPartner | thirdParty
    ec_contribution   REAL,               -- EUR to this organisation (NULL for unfunded roles)
    total_cost        REAL,               -- this organisation's eligible cost
    project_ec_max    REAL,               -- EU contribution to the whole project
    sme               INTEGER,            -- CORDIS SME flag for the organisation
    org_legal_name    TEXT,
    org_vat           TEXT,
    org_country       TEXT,
    partners          INTEGER,            -- other organisations in the consortium
    start_date        TEXT,
    end_date          TEXT,
    status            TEXT,               -- SIGNED | CLOSED | TERMINATED
    is_eic            INTEGER NOT NULL DEFAULT 0,  -- EIC / SME Instrument
    is_mission_ocean  INTEGER NOT NULL DEFAULT 0,  -- Mission "Restore our Ocean and Waters"
    categories        TEXT,               -- JSON list of euroSciVoc fields
    url               TEXT,
    PRIMARY KEY (startup_id, project_id, role)
);

-- CPC classification codes of each patent we hold, with ocean-technology tagging
CREATE TABLE IF NOT EXISTS patent_classes (
    startup_id         INTEGER NOT NULL REFERENCES startups(id) ON DELETE CASCADE,
    publication_number TEXT NOT NULL,
    cpc_code           TEXT NOT NULL,
    ocean_group        TEXT,             -- aquaculture | seaweed | ocean-energy | vessels | ship-emissions | marine-cleanup | ocean-sensing | marine-bio | NULL
    PRIMARY KEY (startup_id, publication_number, cpc_code)
);

-- EU BlueInvest Project Pipeline (public showcase of blue-economy SMEs); doubles as a discovery list
CREATE TABLE IF NOT EXISTS blueinvest_profiles (
    other_id         INTEGER PRIMARY KEY, -- BlueInvest profile id
    name             TEXT NOT NULL,
    summary          TEXT,
    trl              INTEGER,
    trl_text         TEXT,
    sector           TEXT,
    company          TEXT,                -- detail page only
    country          TEXT,                -- detail page only
    financial_needs  TEXT,                -- detail page only (free text)
    funding_sought_eur REAL,              -- largest EUR amount in financial_needs (parsed; medium confidence)
    website          TEXT,                -- detail page only
    startup_id       INTEGER REFERENCES startups(id) ON DELETE SET NULL,  -- matched startup in our DB
    url              TEXT NOT NULL,
    fetched_at       TEXT NOT NULL DEFAULT (datetime('now'))
);

CREATE INDEX IF NOT EXISTS idx_grants_startup ON eu_grants(startup_id);
CREATE INDEX IF NOT EXISTS idx_blueinvest_startup ON blueinvest_profiles(startup_id);

-- Peers outside our DB: similar companies from the EU BlueInvest pipeline (competitor / comparison universe)
CREATE TABLE IF NOT EXISTS startup_external_peers (
    startup_id  INTEGER NOT NULL REFERENCES startups(id) ON DELETE CASCADE,
    source      TEXT NOT NULL,          -- blueinvest
    external_id TEXT NOT NULL,
    name        TEXT NOT NULL,
    similarity  REAL NOT NULL,
    shared_tags TEXT,                   -- JSON list
    trl         INTEGER,
    sector      TEXT,
    url         TEXT,
    PRIMARY KEY (startup_id, source, external_id)
);

-- ---------------------------------------------------------------------------
-- Refresh pipeline run log (Modules/DataAPIs/refresh.py). A run with status 'running' is the lock.
-- ---------------------------------------------------------------------------
CREATE TABLE IF NOT EXISTS refresh_runs (
    id          INTEGER PRIMARY KEY,
    kind        TEXT NOT NULL DEFAULT 'refresh' CHECK (kind IN ('refresh','agent','snapshot')),
    tier        TEXT,                   -- daily (free sources) | full (also spends SerpApi / PDL credits)
    trigger     TEXT NOT NULL DEFAULT 'cli',  -- cli | api | timer
    status      TEXT NOT NULL CHECK (status IN ('running','ok','partial','error')),
    started_at  TEXT NOT NULL DEFAULT (datetime('now')),
    finished_at TEXT,
    summary     TEXT                    -- JSON: steps ok/error/skipped, row changes
);

CREATE TABLE IF NOT EXISTS refresh_steps (
    run_id      INTEGER NOT NULL REFERENCES refresh_runs(id) ON DELETE CASCADE,
    step        TEXT NOT NULL,
    seq         INTEGER NOT NULL,
    status      TEXT NOT NULL CHECK (status IN ('running','ok','error','skipped')),
    started_at  TEXT NOT NULL DEFAULT (datetime('now')),
    finished_at TEXT,
    duration_s  REAL,
    counts      TEXT,                   -- JSON: row changes per table during the step
    detail      TEXT,                   -- error message or skip reason
    PRIMARY KEY (run_id, step)
);

-- ---------------------------------------------------------------------------
-- Unified model: 3 tables (Modules/DataAPIs/unify.py). Entities, facts about them in the Agent's fact
-- format, and assessments computed from those facts. Built from the tables above after each refresh;
-- once main reads these (or the compatibility views from unify.py), the older tables can be dropped.
-- ---------------------------------------------------------------------------

-- One row per real-world thing. Startup entities keep the startup's id; others get ids from 100000.
CREATE TABLE IF NOT EXISTS entities (
    id             INTEGER PRIMARY KEY,
    key            TEXT NOT NULL UNIQUE,        -- stable identity, e.g. startup:notpla, investor:lowercarbon-capital
    kind           TEXT NOT NULL CHECK (kind IN ('startup','candidate','investor','person','organisation','funding_call')),
    slug           TEXT,
    name           TEXT NOT NULL,
    website        TEXT,
    domain         TEXT,                        -- dedupe key (the Agent's website_domain)
    country        TEXT,
    city           TEXT,
    sector         TEXT,                        -- startups: curated sector; candidates: BlueInvest sector
    blue_sector    TEXT,                        -- Agent vocabulary (vocab.BLUE_SECTORS)
    tagline        TEXT,
    description    TEXT,
    founded_year   INTEGER,
    stage          TEXT,
    pipeline_stage TEXT,
    company_number TEXT,                        -- UK Companies House
    lei            TEXT,
    vat            TEXT,
    cordis_id      TEXT,
    blueinvest_id  TEXT,
    pdl_id         TEXT,
    sec_cik        TEXT,
    created_at     TEXT NOT NULL DEFAULT (datetime('now')),
    updated_at     TEXT NOT NULL DEFAULT (datetime('now'))
);

-- One row per piece of evidence, in the Agent's fact format (startup_agent/facts.py) plus provenance.
CREATE TABLE IF NOT EXISTS facts (
    id                INTEGER PRIMARY KEY,
    entity_id         INTEGER NOT NULL REFERENCES entities(id) ON DELETE CASCADE,
    section           TEXT NOT NULL,            -- Agent schema section A-J; X = StartupGo extension
    field             TEXT NOT NULL,            -- Agent field (dev_stage, founders, grants, ...) or extension field
    value             TEXT,                     -- JSON: scalar, list or object (e.g. a round or a pilot)
    related_entity_id INTEGER REFERENCES entities(id) ON DELETE SET NULL,  -- investor in a round, founder, ...
    evidence          TEXT,                     -- verbatim quote or filing/registry text
    source_url        TEXT,
    source_type       TEXT NOT NULL,            -- registry | grant_db | eu_projects | patent | news | website | pitch_deck | manual
    source_name       TEXT NOT NULL,            -- which API, table or the Agent produced it
    status            TEXT NOT NULL CHECK (status IN ('verified','claimed','inferred')),
    confidence        REAL NOT NULL,
    retrieved_at      TEXT,
    observed_on       TEXT,                     -- when the fact was true
    is_current        INTEGER NOT NULL DEFAULT 1
);

-- One row per scoring run per entity (Stage 2 output), kept over time.
CREATE TABLE IF NOT EXISTS assessments (
    id                 INTEGER PRIMARY KEY,
    entity_id          INTEGER NOT NULL REFERENCES entities(id) ON DELETE CASCADE,
    assessed_at        TEXT NOT NULL,
    engine             TEXT NOT NULL,           -- seed-estimate | analyst | startupgo-pipeline | agent
    assessor           TEXT,
    confidence         TEXT,                    -- low | medium | high (analyst assessments)
    trl INTEGER, brl INTEGER, crl INTEGER, iprl INTEGER, tmrl INTEGER, frl INTEGER,  -- 1-9
    oir INTEGER,                                -- Ocean Impact Readiness 1-5
    levels_basis       TEXT,                    -- JSON: facts and rules behind each level
    navigator_kpis     TEXT,                    -- JSON: {"B2": {"level": 2, "claim": "...", "source_url": "..."}}
    criteria           TEXT,                    -- JSON: 10 investment criteria, score 1-5 + confidence
    investment_score   REAL,
    overall_confidence REAL,
    red_flags          TEXT,                    -- JSON list
    data_gaps          TEXT,                    -- JSON list
    next_steps         TEXT,                    -- JSON list
    peers              TEXT,                    -- JSON list
    features           TEXT,                    -- JSON: StartupGo features {name: {value, text, evidence}}
    rationale          TEXT,
    judge_status       TEXT,
    UNIQUE (entity_id, engine, assessed_at)
);

CREATE INDEX IF NOT EXISTS idx_entities_kind ON entities(kind);
CREATE INDEX IF NOT EXISTS idx_entities_domain ON entities(domain);
CREATE INDEX IF NOT EXISTS idx_facts_entity ON facts(entity_id, section, field);
CREATE INDEX IF NOT EXISTS idx_assessments_entity ON assessments(entity_id, engine, assessed_at);
