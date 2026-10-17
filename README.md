# Startup Go

Deal intelligence for VCs investing in ocean and deep-tech startups. Startups are ranked on:

- **Technology readiness (TRL)** and **business readiness (BRL)**: the full KTH Innovation Readiness Level (CRL, TRL, BRL, IPRL, TMRL, FRL, each 1–9)
- **Ocean impact readiness**: evidence (0–4) against the Ocean Impact Navigator's 30 KPIs in 6 impact areas
- **Investment potential**: a transparent blend of readiness, ocean impact and funding momentum, minus a penalty when readiness dimensions are badly out of balance

Background research, the DeepTree feature notes and paper references are in [RESEARCH.md](RESEARCH.md).

## Structure

```
Frontend/   React + TypeScript (Vite): search, assess, matching, pipeline, compare, methodology
Backend/    Python (FastAPI): REST API + scoring model (app/scoring.py)
DB/         SQL: schema.sql + seed.sql (SQLite in dev, written to port to PostgreSQL)
Modules/    uv workspace (one uv.lock, one .venv) for the Python modules below
  Scraper/  Python: public page fetching (HTTP or stealth Chrome) and startup discovery (Wellfound, OSM, generic)
  Agent/    Python: builds evidence-backed startup entries per the Ocean Opportunity Radar extraction
            schema (facts → TRL/BRL/OIR, investment criteria, next steps). See Modules/Agent/README.md
```

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

### Frontend layout

```
Frontend/src/
  pages/            one file per route (DealFlow, StartupPage, Compare, Assess, Matching, Pipeline, Methodology)
  components/ui/    generic, reusable building blocks, one per file: import from "@/components/ui"
                    (PageHeader, Section, StatCard, EmptyState, BackLink, Meter, BandBadge, FilterSelect, TextField, …)
  components/       app-specific components shared by pages (SearchBar, StageSelect, assess/, matching/, …)
  lib/              logic and hooks (search, sort, matching, assessment, format, useDealFlowSearch, …) + tests
  api/              client.ts + types.ts (mirrors Backend/app/schemas.py)
  state/            AppData: startups and frameworks, loaded once
```

Styling is Tailwind v4 only (`src/index.css`: design tokens, theme and base element styles).
Colours, radii and shadows come from the design tokens (`bg-surface`, `text-fg-2`, `border-line`,
`text-muted`, `rounded-card`, `shadow-card`, …), so light/dark switches automatically.
- **Spacing:** the unit is 4px (`p-4` = 16px).
- **Type scale:** `text-label`, `text-sm`, `text-small`, `text-h1`, …
- **Breakpoints:** they match the old media queries (`max-md:` = below 761px).
- **Shared patterns:** buttons, inputs, cards, tables, chips and toggles are class helpers in
  `components/ui/styles.ts` (`button("primary")`, `control`, `card`, `th`/`td`, …). Use those
  instead of repeating the utility lists.

Use the `@/` import alias across folders and `./` within one. Build pages from `components/ui` and
keep a page's single-use sub-components in the page file; move a piece into `components/` once a
second page needs it.

## Run locally

Backend (Python 3.11, managed with [uv](https://docs.astral.sh/uv/)). It creates `DB/startupgo.db` from the SQL files on first start:

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

Agent and Scraper (Python 3.11, [uv](https://docs.astral.sh/uv/)). One shared environment for both:

```bash
cd Modules
uv sync --all-packages
cp Agent/.env.example Agent/.env     # add GEMINI_API_KEY
uv run --package startup-agent startup-agent graph --name "Origin by Ocean" --website https://www.originbyocean.com
```

To reset the database after editing `DB/*.sql`, delete `DB/startupgo.db` and restart the backend.

## Tests

```bash
cd Backend && uv run pytest                   # scoring + API
cd Frontend && npm run check                  # typecheck + lint + unit tests
cd Frontend && npm run format                 # prettier
cd Modules/Agent && uv run pytest             # agent: extraction, scoring, judge, workflow
cd Modules/Scraper && uv run python -m unittest discover -s tests -t .   # scraper
```

## API

| Method | Path | Purpose |
|--------|------|---------|
| GET | `/api/startups` | List with scores. Filters: `q`, `sector`, `country`, `stage`, `pipeline_stage`, `impact_area` (A–F), `min_trl`, `min_brl`, `min_potential`. Sort: `potential`, `readiness`, `ocean`, `momentum`, `trl`, `brl`, `name` |
| POST | `/api/startups` | Create a startup with its first assessment (and optional funding round) |
| GET | `/api/startups/{slug}` | Profile: level text, ocean KPIs, funding rounds, sources, notes |
| POST | `/api/startups/{slug}/assessments` | Add a dated readiness + ocean-impact assessment |
| POST | `/api/scoring/preview` | Score unsaved levels/KPIs (powers the live preview) |
| PATCH | `/api/startups/{slug}/pipeline` | Move a deal between pipeline stages |
| POST | `/api/startups/{slug}/notes` | Add an analyst note |
| GET | `/api/compare?slugs=a,b,c` | Up to 3 profiles |
| GET | `/api/filters` | Filter options |
| GET | `/api/frameworks` | KTH IRL levels, Navigator KPIs, scoring weights |
| POST | `/api/search` | `{ "query": "..." }` or `{ "filters": {...} }` → applied filters + matching startups (sorted in the UI). 501 until the search wrapper is connected (see below) |

Interactive docs: http://localhost:8000/docs

## Search

The deal-flow search bar sends what the user types to `POST /api/search` as `{ "query": ... }`.
Removing a filter chip or changing a dropdown sends `{ "filters": ... }` instead, and the edited
filters are kept in the URL (`f=`). The response carries the startups, the filters the search
applied (shown as chips, or `null`) and an optional `notice`.

The endpoint delegates to a `SearchWrapper` (`Backend/app/search.py`), the seam for the RAG /
vector search. Until one is connected, `/api/search` returns **501** and the Deal flow page shows
the error for searches. Browsing with no search still uses `GET /api/startups`. To connect a real
search, implement `SearchWrapper.search(query=..., filters=...)` and return it from
`get_search_wrapper()`.

Backend settings go in `Backend/.env` (template: `Backend/.env.example`). Variables already set in
the shell take precedence. Restart the backend after editing `.env`, since `--reload` only watches
Python files.

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
