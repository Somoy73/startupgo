# DataAPIs: scrapers for data-apis.md

One scraper per API listed in [../data-apis.md](../data-apis.md). Python 3 stdlib only; HTTP goes through `curl`, which uses the system trust store.

```bash
cd DataAPIs
python3 run.py                    # all free (no-key) scrapers -> data/<name>.json (+ data/_summary.json)
python3 run.py openalex           # one scraper
python3 run.py openalex search="sea ice" per-page=10   # override any upstream param
python3 run.py --all              # also key/paid ones (skipped unless their env var is set)
python3 run.py --list             # names, access level, endpoints
python3 run.py --docs             # regenerate PARAMETERS.md
```

Each `data/<name>.json` holds `{params, full_size_bytes, sample}`; the sample is trimmed (10 list items, 600-char strings).
[PARAMETERS.md](PARAMETERS.md) lists every upstream parameter per API.

Env vars for the key-based ones: `SEC_USER_AGENT`, `PDL_API_KEY`, `OPENCORPORATES_API_KEY`, `COMPANIES_HOUSE_KEY`, `EPO_KEY`+`EPO_SECRET`,
`PATENTSVIEW_KEY`, `LENS_TOKEN`, `GITHUB_TOKEN` (optional), `S2_API_KEY` (optional), `PRODUCTHUNT_TOKEN`, `NEWSAPI_KEY`, `BRAVE_API_KEY`,
`TAVILY_API_KEY`, `EXA_API_KEY`, `FIRECRAWL_API_KEY`, `CRUNCHBASE_KEY`, `HILMA_KEY`.
Paid vendors with no public docs (Harmonic, Dealroom, PitchBook, Tracxn, Orbis) are stubs that raise until you add a contract schema.
Google Patents needs BigQuery and is not callable over plain HTTP.

## Loading into the database

```bash
python3 ingest.py               # per-startup pulls for every startup in DB, funding calls, market data, gap analysis
python3 ingest.py --gaps-only   # rebuild the parameter catalogue, per-startup status and GAPS.md only
python3 ingest.py --gdelt       # also query GDELT per startup (slow)
python3 ingest.py --gaps-only --serpapi   # only SerpApi enrichment (2 searches/startup) + gaps
```

Keys can go in `DataAPIs/.env` (gitignored, `KEY=value` per line); real environment variables take precedence.

Writes to `DB/startupgo.db` (creates it from `DB/schema.sql` + `DB/seed.sql` if missing). With `SERPAPI_KEY` set, patents still load when the free Google Patents endpoint is blocked, and each startup gets a Google search (website, knowledge panel: founded, HQ, employees, founders) and a Google Jobs search (hiring signals).

| Table | Holds |
|---|---|
| `data_sources` | Every scraper, its access level and last status |
| `raw_fetches` | Every API call: params, status, error, trimmed payload, timestamp |
| `startup_external_ids` | LEI, YC slug, SEC CIK, Wikidata QID per startup |
| `startup_signals` | Patents, papers, news, HN launches, repos, web history, website text, registry and SEC filings, each with `match_confidence` |
| `field_suggestions` | Candidate values for curated `startups` columns (never auto-applied) |
| `funding_opportunities` | EU calls (SEDIA), Grants.gov, UKRI projects, TED tenders |
| `market_indicators` | World Bank and Eurostat series |
| `assessment_parameters` | The 455 items of `parameters.txt` (A–U) with coverage: auto / partial / missing |
| `startup_parameter_status`, view `startup_gaps` | Per startup: filled / proxy / empty / not-collectable |

[GAPS.md](GAPS.md) is the generated gap report.
