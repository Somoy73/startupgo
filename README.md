# Startup Go

Deal intelligence for VCs investing in ocean and deep-tech startups. Startups are ranked on:

- **Technology readiness (TRL)** and **business readiness (BRL)**: the full KTH Innovation Readiness Level (CRL, TRL, BRL, IPRL, TMRL, FRL, each 1–9)
- **Ocean impact readiness**: evidence (0–4) against the Ocean Impact Navigator's 30 KPIs in 6 impact areas
- **Investment potential**: a transparent blend of readiness, ocean impact and funding momentum, minus a penalty when readiness dimensions are badly out of balance

Background research, the DeepTree feature notes and paper references are in [RESEARCH.md](RESEARCH.md).

## Structure

```
Frontend/   React + TypeScript (Vite): deal flow, startup profile, compare, pipeline board, methodology
Backend/    Python (FastAPI): REST API + scoring model (app/scoring.py)
DB/         SQL: schema.sql + seed.sql (SQLite in dev, written to port to PostgreSQL)
```

## Run locally

Backend (Python 3.11+). It creates `DB/startupgo.db` from the SQL files on first start:

```bash
cd Backend
python3 -m venv .venv && .venv/bin/pip install -r requirements-dev.txt
.venv/bin/uvicorn app.main:app --reload --port 8000
```

Frontend (Node 18+). The dev server proxies `/api` to `:8000`:

```bash
cd Frontend
npm install
npm run dev        # http://localhost:5173
```

To reset the database after editing `DB/*.sql`, delete `DB/startupgo.db` and restart the backend.

## Tests

```bash
cd Backend && .venv/bin/python -m pytest      # scoring + API
cd Frontend && npm run build                  # typecheck + production build
```

## API

| Method | Path | Purpose |
|--------|------|---------|
| GET | `/api/startups` | List with scores. Filters: `q`, `sector`, `country`, `stage`, `pipeline_stage`, `impact_area` (A–F), `min_trl`, `min_brl`, `min_potential`. Sort: `potential`, `readiness`, `ocean`, `momentum`, `trl`, `brl`, `name` |
| GET | `/api/startups/{slug}` | Profile: level text, ocean KPIs, funding rounds, sources, notes |
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
3. Natural-language search: parse "seed-stage kelp startups in Europe with TRL ≥ 6" into filters
4. Investor ↔ startup thesis matching (DeepTree-style buyer discovery)
5. IC memo generation from a profile
6. Postgres + auth + multi-user notes
