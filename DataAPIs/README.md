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
