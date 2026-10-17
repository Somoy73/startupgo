# DataAPIs: scrapers, refresh pipeline and features

One scraper per API listed in [../../data-apis.md](../../data-apis.md), the refresh pipeline that loads them into the
database, and the success-prediction features. A member of the uv workspace in `Modules/` (package `startup-data`,
scripts only). Python 3.11+, standard library plus `pypdf`; HTTP goes through `curl`, which uses the system trust store.

## Refresh pipeline (start here)

```bash
cd Modules && uv sync --all-packages && cd DataAPIs     # or: pip install -r requirements.txt
uv run python refresh.py                  # daily tier: free sources only, into the runtime DB
uv run python refresh.py run --tier full  # also SerpApi + People Data Labs (credits) + BlueInvest re-crawl
uv run python refresh.py run --steps cordis,features,gaps   # selected steps (`refresh.py steps` lists them)
uv run python refresh.py status           # recent runs: per-step status, duration, row changes, errors
uv run python refresh.py snapshot         # copy the runtime DB to DB/startupgo.db + CSVs + GAPS.md, then commit
```

| Location | What | In git |
|---|---|---|
| `DB/runtime/startupgo.db` | Live DB every script writes to (override with `STARTUPGO_DB`); copied from the snapshot on first use | no |
| `DB/runtime/config/{agent,search}/config.toml` | Generated from main's `Modules/Agent` and `Modules/Search` configs with only the paths changed (runtime DB, runtime index, runtime Agent output); `.env` is a symlink to main's | no |
| `DB/runtime/rag_storage/`, `DB/runtime/agent_output/`, `DB/runtime/GAPS.md` | Runtime search index, Agent entries, gap report | no |
| `DB/startupgo.db`, `csv/`, `GAPS.md` | Snapshot for commits; changed only by `refresh.py snapshot` | yes |

Each run is logged in `refresh_runs` / `refresh_steps`; a run marked `running` is the lock (`--force` takes over a dead
one). A failing source marks its step `error` and the run continues (`partial`); steps without their key or tool are
`skipped`. Main's Agent, Search and Scraper code is not modified: the search step runs main's `process-storage`
with the generated `--config`, and the Agent can be pointed at the runtime data the same way:
`uv run startup-agent --config ../DB/runtime/config/agent/config.toml graph --mode evaluation` (from `Modules/`,
after `refresh.py configs`).

## Single scrapers

```bash
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

Keys can go in `Modules/DataAPIs/.env` (gitignored, `KEY=value` per line); real environment variables take precedence.

Writes to the runtime DB (`DB/runtime/startupgo.db`, see above), never to the tracked snapshot. With `SERPAPI_KEY` set, patents still load when the free Google Patents endpoint is blocked, and each startup gets a Google search (website, knowledge panel: founded, HQ, employees, founders) and a Google Jobs search (hiring signals).

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

[GAPS.md](GAPS.md) is the gap report of the committed snapshot; refreshes write theirs to `DB/runtime/GAPS.md`.

## Success-prediction features

```bash
uv sync --all-packages (in Modules/)       # pypdf, for SH01 PDFs (or: pip install -r requirements.txt)
python3 features.py                        # fetch UK SH01 + officer appointments, SEC Form D; compute features
python3 features.py --offline              # recompute from the DB only
```

Parameters follow Potanin et al. 2023 ([arXiv:2309.15552](https://arxiv.org/abs/2309.15552)): rounds, investors, founders, categories.
They are extended with the team's ranked parameter list and ocean deep-tech additions (distress, down rounds, founder retention, evidence conflicts).
Investor tiers are analyst judgments in [investor_tiers.json](investor_tiers.json); edit them freely.

| Table | Holds |
|---|---|
| `funding_events` | One timeline from announced rounds, UK SH01 allotments (shares, price paid, total shares, implied post-money), SEC Form D (amount sold, investor count), PDL aggregate |
| `people`, `startup_people`, `person_ventures` | Officers and founders, and every other company each has directed (serial-founder evidence) |
| `investors`, `startup_investors` | Investors per startup with kind, tier score and follow-on count |
| `feature_definitions`, `startup_features` | Feature catalogue and point-in-time values with evidence; missing = no row, never 0 |
| `startup_peers` | Weighted tag similarity between startups |

API (FastAPI, see `/docs`): `/api/features/catalog`, `/api/features?format=json|csv`, and per startup
`/api/startups/{slug}/features|rounds|founders|investors|peers`.

## EU and ocean-specific sources

```bash
python3 ingest_eu.py                          # CORDIS grants, patent CPC classes, BlueInvest pipeline, FR/NO registers
python3 ingest_eu.py --only=cordis,patents    # selected steps: cordis, patents, retag, blueinvest, registers
python3 ingest_eu.py --blueinvest-refresh     # re-crawl the 36-page BlueInvest pipeline list
python3 features.py --offline                 # then recompute features
```

All keyless. Left out on purpose because of coverage limits: the EU Blue Economy Observatory (data to 2023, EU-27 only,
established sectors only), EMFAF beneficiary lists (per-country formats), startup directories and port maps.

| Table | Holds |
|---|---|
| `eu_grants` | CORDIS projects per startup: role, own EU contribution, SME flag, EIC/SME Instrument and Mission Ocean flags, topics |
| `patent_classes` | CPC codes of each patent with ocean-technology group (aquaculture, seaweed, marine-bio, ocean-energy, vessels, ship-emissions, marine-cleanup, ocean-sensing) |
| `blueinvest_profiles` | The EU BlueInvest Project Pipeline (~718 blue-economy SMEs, TRL, sector); detail fields for profiles matched to our startups |

French (`fr_recherche_entreprises`) and Norwegian (`no_brreg`) registers run only for startups in those countries.
API: `/api/startups/{slug}/grants`, `/api/startups/{slug}/patents`, `/api/discovery/blueinvest?q=&sector=&min_trl=&matched_only=`.

## Founders, hiring and competitors (closing public-data gaps)

```bash
python3 ingest_gaps.py                  # non-UK founders/boards (PDL person search), job boards, BlueInvest peer universe
python3 ingest_gaps.py --only=jobs      # steps: founders, jobs, peers
python3 ingest_gaps.py --founders-all   # also PDL lookups for UK startups (more credits)
python3 features.py --offline && python3 ingest.py --gaps-only
```

- Founders: UK from Companies House; elsewhere PDL person search (two queries per startup, at most 6 credits).
  Only name, role, dates, founder/owner/CEO/MD prior roles and degrees are stored; emails, phones, sex and profile URLs are dropped.
- Boards: Companies House directors (UK), SEC Form D directors and executive officers (US), PDL board titles.
- Hiring: the company's own job board (Ashby, Greenhouse, Lever, Workable, Recruitee, Personio), found from its careers page or name.
- Competitors: TF-IDF similarity against the 718 BlueInvest profiles (`startup_external_peers`).
- Gap statuses now include `not-applicable` (e.g. GitHub activity for hardware/biotech startups); missing still means unknown, never zero.

API: `/api/startups/{slug}/founders?founders_only=false` (with education and ventures), `/api/startups/{slug}/peers/blueinvest`.
