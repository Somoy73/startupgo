# Startup Go

<img width="1448" height="905" alt="Start_View" src="https://github.com/user-attachments/assets/89242d64-1130-4779-a6ef-dc9b017ef881" />

Deal intelligence for VCs investing in ocean and deep-tech startups. Startups are ranked on:

- **Technology readiness (TRL)** and **business readiness (BRL)**: the full KTH Innovation Readiness Level (CRL, TRL, BRL, IPRL, TMRL, FRL, each 1–9)
- **Ocean impact readiness**: evidence (0–4) against the Ocean Impact Navigator's 30 KPIs in 6 impact areas
- **Investment potential**: a transparent blend of readiness, ocean impact and funding momentum

Background research, the DeepTree feature notes and paper references are in [RESEARCH.md](RESEARCH.md).

## Structure

```
Frontend/   React + TypeScript (Vite): search, assess, matching, pipeline, compare, methodology
Backend/    Python (FastAPI): REST API + scoring model (app/scoring.py)
DB/         startupgo_unified.db: the database (entities, facts, assessments; schema and read views in unified.sql).
            schema.sql + seed.sql: the DataAPIs pipeline's tables, from which unify.py builds it
Modules/    uv workspace (one uv.lock, one .venv) for the Python modules below
  Scraper/  Python: public page fetching (HTTP or stealth Chrome) and startup discovery (Wellfound, OSM, generic)
  Agent/    Python: builds evidence-backed startup entries per the Ocean Opportunity Radar extraction
            schema (facts → TRL/BRL/OIR, investment criteria, next steps); stores judge-approved entries
            in the DB; `startup-agent pipeline` researches startups still to assess. See Modules/Agent/README.md
  Search/   Python: natural-language startup search with LightRAG and NVIDIA models; process-storage
            turns the DB + agent entries into its vector and graph storage; N-hop graphs for matching.
            See Modules/Search/README.md
  DataAPIs/ Python: public API scrapers and refresh.py, the whole data pipeline as one command
```

## Pipeline

```
DataAPIs: registries, patents, funding, people, jobs ─┐
Scraper: Wellfound, directories (discovered leads)   ─┴→ candidates: name + website + info
  → Agent: research → judge → evaluation → judge        (startup-agent pipeline)
  → DB: entities (startups) · assessments (one per scoring run: six KTH levels, OIR, criteria, investment score)
        · facts (evidence in the Agent's format: KPIs, rounds, sources, ...)
  → process-storage: LightRAG knowledge graph + vectors
  → Backend: search (+ filters) · assess (+ research jobs) · match (N-hop graph)
```

- **Run it all:** `cd Modules/DataAPIs && uv run python refresh.py run --tier full` (sources → `features`, `gaps` → `unify` →
  `agent` → `search_index`), or only the agent and the index: `refresh.py run --steps agent,search_index`. Both write the
  runtime DB (`DB/runtime/`); `search_index` also writes its 3-table copy, `DB/runtime/startupgo_unified.db`, and indexes it.
  Serve that copy, with its search index and agent settings (research jobs write to the copy, which the next refresh replaces):

  ```bash
  cd Backend && STARTUPGO_DB=../DB/runtime/startupgo_unified.db \
    STARTUPGO_SEARCH_CONFIG=../DB/runtime/config/search/config.toml \
    STARTUPGO_AGENT_CONFIG=../DB/runtime/config/agent/config.toml \
    uv run uvicorn app.main:app --host 0.0.0.0 --port 8000
  ```

  A running Backend picks up the index the next refresh writes; no restart needed.
- **Agent only:** `cd Modules/Agent && uv run startup-agent pipeline` (`--dry-run` lists the candidates first): startups
  without a usable score in `assessments` are researched, and each run's scores are stored there (`engine = 'agent'`).
  For startups discovered on a page instead: `startup-agent pipeline --discover-url https://wellfound.com/startups/industry/clean-technology --limit 5`,
  then `cd ../Search && uv run process-storage` for search.
- **One startup from the API:** `POST /api/research` queues a job for a startup without a score; the new assessment is in the
  `assessments` table when it finishes. A startup that already has a score isn't researched (409).

## Features

| Page | What it does |
|------|--------------|
| **Deal flow** (`/`) | Smart search: type `seed kelp in europe trl>=5` and it becomes removable filter chips (stage, sector, country, region, impact area, pipeline, minimum levels, free text). The query lives in the URL, so searches can be shared |
| **Quick search** (⌘K / Ctrl+K) | Jump to any startup, run a deal-flow search, or start an assessment |
| **Assess** (`/assess`, `/assess/:slug`) | Score a new or existing startup: KTH IRL 1–9 per dimension with level definitions, Ocean Impact Navigator KPI evidence 0–4 with claims and sources, and a live score preview from the backend model. Each save is a dated snapshot |
| **Matching** (`/matching`) | Define an investor thesis (stages, sectors, regions, impact areas, minimum TRL/BRL/ocean impact) and rank startups by fit + investment potential, with a per-criterion explanation. Presets included; custom theses are saved in the browser |
| **Startup profile** | Scores, readiness profile, ocean impact, funding, notes, sources |
| **Pipeline / Compare / Methodology** | Kanban deal stages, side-by-side comparison, scoring documentation |

Frontend layout: `src/lib/` holds pure, unit-tested logic (`search.ts`, `matching.ts`, `assessment.ts`); `src/state/AppData.tsx` loads the startup list and frameworks once for all pages; `src/components/` and `src/pages/` are presentation.

## Run locally

Backend (Python 3.11, managed with [uv](https://docs.astral.sh/uv/)). It serves `DB/startupgo_unified.db` (`STARTUPGO_DB` overrides it; a
missing file starts as a copy of it) and applies `DB/unified.sql` on start:

```bash
cd Backend
uv sync            # creates .venv with runtime + dev dependencies
uv run uvicorn app.main:app --reload --host 0.0.0.0 --port 8000
```

Frontend (Node 18+). The dev server proxies `/api` to `:8000`:

```bash
cd Frontend
npm install
npm run dev        # http://localhost:5173
```

Agent, Scraper and Search (Python 3.11, [uv](https://docs.astral.sh/uv/)). One shared environment:

```bash
cd Modules
uv sync --all-packages
cp Agent/.env.example Agent/.env     # add GEMINI_API_KEY
uv run --package startup-agent startup-agent graph --name "Origin by Ocean" --website https://www.originbyocean.com
cp Search/.env.example Search/.env   # add CHAT_API_KEY, EMBEDDING_API_KEY
cd Search && uv run process-storage  # DB + agent entries -> LightRAG storage, for POST /api/startups/search
```

`DB/unified.sql` is generated: `cd Modules/DataAPIs && python3 unify.py --sql ../../DB/unified.sql`. The Backend applies it
on every start, so view changes reach the existing database.

## Tests

```bash
cd Backend && uv run pytest                   # scoring + API
cd Frontend && npm run check                  # typecheck + lint + unit tests
cd Frontend && npm run format                 # prettier
cd Modules/Agent && uv run pytest             # agent: extraction, scoring, judge, workflow
cd Modules/Scraper && uv run python -m unittest discover -s tests -t .   # scraper
cd Modules/Search && uv run pytest            # search: documents, process-storage, LightRAG with fake models
```

## API

| Method | Path | Purpose |
|--------|------|---------|
| GET | `/api/startups` | List with scores: `scores` (investment potential, 0–100) and `investment`, the agent's Investment Score Matrix (10 criteria, 1–5): the agent's latest accepted assessment, else the agent's rubric and weights on the startup's facts, so it matches the agent's entries. Filters: `q`, `sector`, `country`, `stage`, `pipeline_stage`, `impact_area` (A–F), `min_trl`, `min_brl`, `min_potential`. Sort: `potential`, `investment`, `readiness`, `ocean`, `momentum`, `trl`, `brl`, `name` |
| POST | `/api/startups/search` | Natural-language search, e.g. `{"query": "seaweed packaging replacing plastic", "filters": {"min_trl": 5, "impact_area": "B"}}`: database startups (`results`, with `relevance` and the `matched` graph entities) and agent-only entries (`entries`). `filters` (optional) takes the `GET /api/startups` filters. 503 until `process-storage` has run |
| GET | `/api/startups/{slug}/graph` | Matching: the knowledge graph within `hops` (0–3, default 2) of the startup (`nodes`, `edges`) and the startups it reaches, most shared entities first |
| POST | `/api/match/graph` | Matching from a thesis: `{"thesis": "kelp carbon removal", "hops": 1, "filters": {...}}` seeds the graph with the entities the thesis retrieves |
| POST | `/api/research` | Queue the agent on `{"slug": ...}` or a new `{"name", "website"}` (optional `business_id`, `urls`). 202 with the job; 409 if the startup (by slug or website domain) already has a score |
| GET | `/api/research/{id}` | Job status (`queued`, `running`, `done`, `error`) and result: scores, judge review, whether it was stored |
| GET | `/api/startups/{slug}/research` | The agent's latest accepted assessment of the startup, when it last ran (any verdict), and its latest job since the Backend started |
| POST | `/api/startups` | Create a startup with its first assessment (and optional funding round) |
| GET | `/api/startups/{slug}` | Profile: level text, ocean KPIs, funding rounds, sources, notes |
| POST | `/api/startups/{slug}/assessments` | Add a dated readiness + ocean-impact assessment |
| POST | `/api/scoring/preview` | Score unsaved levels/KPIs (powers the live preview) |
| PATCH | `/api/startups/{slug}/pipeline` | Move a deal between pipeline stages |
| POST | `/api/startups/{slug}/notes` | Add an analyst note |
| GET | `/api/compare?slugs=a,b,c` | Up to 3 profiles |
| GET | `/api/filters` | Filter options |
| GET | `/api/frameworks` | KTH IRL levels, Navigator KPIs, scoring weights |

Interactive docs: http://localhost:8000/docs

## Data caveat

Funding facts in `DB/seed.sql` come from public announcements, each with a source URL. **Readiness and
impact-evidence levels are seed estimates (confidence `low`)** and must be validated with the companies.

## Roadmap (backend)

1. Ingestion: import startups and rounds from CSV and public sources; store provenance per field
2. Assessment workflow: founders or analysts submit dated readiness assessments with evidence
3. Persist investor theses server-side (currently browser localStorage)
4. Move search/matching server-side once the dataset outgrows client-side filtering
5. IC memo generation from a profile
6. Postgres + auth + multi-user notes
