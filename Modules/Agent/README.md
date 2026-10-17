# StartupGo Agent

Builds a startup entry that follows the **Ocean Opportunity Radar extraction schema**:
about 60 facts in 10 sections (A–J). Each fact carries evidence: a verbatim quote, its source URL, the
source type, the date it was read, a claimed/verified/inferred status and a confidence. TRL, BRL, Ocean
Impact Readiness, the 10 investment criteria, next steps and first-call questions are then **computed
by code from those facts**. The LLM extracts facts; it never scores.

This module is the agent interface. Page fetching and startup discovery (including Wellfound) live in
the separate `Modules/Scraper` package, which this module depends on.

## Setup

Agent and Scraper are members of one uv workspace (`Modules/pyproject.toml`) with a shared
lockfile and environment (`Modules/.venv`):

```bash
cd Modules
uv sync --all-packages        # one environment for Agent + Scraper (+ pytest)
cp Agent/.env.example Agent/.env   # add GEMINI_API_KEY (or the key named in config.toml)
cd Agent                      # commands below run from here (or: uv run --package startup-agent ... from Modules/)
```

Install or update packages with `uv sync --all-packages` from `Modules/`. A plain `uv sync` inside
`Scraper/` would remove the Agent's packages from the shared environment. `uv run` is safe anywhere.

## Multi-agent workflow (LangGraph)

Two agents connected by a LangGraph graph (`startup_agent/graph.py`):

| Agent | Job |
|-------|-----|
| **Research** | Gathers data. Discovers startups through the scraper (Wellfound, OSM, generic directories), or takes a name and website. Crawls the startup's site, **searches the web** for independent pages about it, fetches those pages through the scraper, and extracts evidence-backed facts into schema entries. |
| **Evaluation** | Assesses. Recomputes TRL, BRL, Ocean Impact Readiness and the 10 investment criteria from the facts, ranks the startups, and summarises each one: strengths, weaknesses, unknown criteria, next steps, data gaps. |

```
--mode both        START → research → evaluation → END   (default)
--mode research    START → research → END
--mode evaluation  START → evaluation → END
```

```bash
# Research one startup, then evaluate it
uv run startup-agent graph --name "Origin by Ocean" --website https://www.originbyocean.com

# Discover startups on Wellfound, research each, evaluate and rank them
uv run startup-agent graph --discover-url https://wellfound.com/startups/industry/aquaculture --limit 5

# Research only (entries are saved; evaluate later)
uv run startup-agent graph --mode research --discover-url https://wellfound.com/startups/industry/aquaculture --limit 5

# Evaluate and rank every saved entry (or pass --entry FILE, repeatable)
uv run startup-agent graph --mode evaluation
```

Entries are saved to `output/startups/<id>.json` and listed in `output/index.json`. The ranking is
printed one line per startup; add `--json` for the full workflow state. Leads without a website,
search failures and other problems are reported but never stop the run.

### Searching the entries

The Backend's natural-language search is the `Search` module (`Modules/Search`, LightRAG). Its
`process-storage` command reads these entries (`output/startups/*.json`) along with the database.
Run it again after saving new entries.

### Web search

The research agent runs the `[search] queries` in `config.toml` (e.g. `"{name}" startup funding
investment`) through an official search API, never by scraping a search engine:

- `provider = "gemini"` (default): Google Search through Gemini grounding, using the same key as the LLM.
  The Gemini API free tier may not include grounding; if every search returns 429, enable billing or
  switch provider.
- `provider = "brave"`: Brave Search API; put the key in `.env` as `BRAVE_API_KEY`.
- `provider = "none"`: website, discovery data and `--url` pages only.

Result pages are fetched through the scraper (robots.txt respected). Login-walled sites (LinkedIn,
Facebook, ...) and the startup's own domain are skipped, and a page is kept only if it mentions the
startup. Its facts then go through the same quote check. Independent pages count as `verified`
sources, and search results are cached.

## Speed and rate limits

Each run ends with a usage line on stderr, e.g.
`usage: LLM 5 request(s), 3 cached; search 1 request(s), 0 cached; 0 retries; 24s waiting for rate limits; tokens in 41,200 / out 3,900 / thinking 0; 2 call(s) skipped (quota exhausted)`.

What keeps a run fast, all in `config.toml`:

| Setting | Effect |
|---------|--------|
| `[llm] section_groups` | Sections extracted together per LLM call. The default groups need **3 calls per startup instead of 10**. |
| `[llm] requests_per_minute` | One pacer shared by extraction, the judge and search. Requests are spaced evenly instead of bursting into 429 errors. Set it to your plan's limit (free tier ≈ 10). |
| `[llm] thinking = "minimal"` | Turns off Gemini's reasoning step, which extraction doesn't need: faster, and no thinking tokens counted against your quota. Ignored automatically if the model rejects it. |
| `[judge] max_research_rounds` | Each judge-requested redo costs more calls; 1 is a good balance. |
| `[judge] check_support` | The judge's quote check is one extra call per startup; `false` skips it. |
| `[search] provider` | `"none"` skips web search entirely. |

When a quota is used up (HTTP 429 with no retry time), the agent stops calling that quota for the rest
of the run instead of retrying. Search and generation are tracked separately, since Google Search
grounding has its own quota. Everything is cached, so a rerun only pays for what failed or changed.

## Single-step commands

```bash
# One startup from its name and website → output/startups/<domain>.json
uv run startup-agent profile --name "Sulapac" --website https://www.sulapac.com

# Known Finnish business ID, plus extra source pages
uv run startup-agent profile --name "Sulapac" --website sulapac.com \
    --business-id 2739393-2 --url https://example-news.fi/sulapac-raises

# Discover startups on a Wellfound collection page; add --profile to build entries for each
uv run startup-agent discover --url https://wellfound.com/startups/industry/clean-technology --limit 5

# Recompute scores/next steps after hand-correcting facts in an entry
uv run startup-agent rescore output/startups/sulapac-com.json

# JSON Schema of an entry, for other teams/services
uv run startup-agent schema --output startup_entry.schema.json
```

From Python:

```python
from pathlib import Path
from startup_agent import AgentSettings, build_agent, build_agent_graph

settings = AgentSettings.load(Path("config.toml"))
agent, fetcher = build_agent(settings)
try:
    workflow = build_agent_graph(agent, weights=settings.weights)
    result = workflow.invoke({"mode": "both", "name": "Sulapac", "website": "https://www.sulapac.com"})
    print(result["assessments"])          # ranked summaries; result["evaluated"] holds full entries
finally:
    fetcher.close()
```

## How it works

1. **Collect sources.** Crawl the homepage and up to `max_pages` same-site pages, picked by how well
   their URL matches each section's keywords (`/team`, `/technology`, `/impact`, `/news`, ...).
   `robots.txt` is respected. Add pages found by web search (see above) and any extra `--url` pages.
   Pages from other domains are typed by domain: CORDIS → `eu_projects`, patent sites → `patent`,
   anything else → `news`. Discovery listings (Wellfound) count as the startup's own `website`
   claims.
2. **Structured data first.** For Finnish companies (`.fi` site, Finland found in section A, or
   `--business-id`), section A comes from the PRH open data API. These facts are `verified` with
   confidence 0.95, and override weaker website claims.
3. **A few LLM calls per startup** (sections grouped per `[llm] section_groups`, or one per section), sending only the pages relevant to those sections and a strict JSON schema (enums for
   anything that feeds a score or match). The prompt (`prompts/`) forces a verbatim quote for every
   value and states that null is a correct answer.
4. **Check the quotes in code.** Each quote must appear in the cited page, after whitespace and
   quote-mark normalisation; "..."-separated fragments must appear in order. Values whose quotes
   aren't found, or that don't match the field type, are dropped and listed under
   `rejected_extractions`.
5. **Status and confidence.** The startup's own pages are `claimed`. News, registries, CORDIS and
   patents are `verified`. LLM classifications (`blue_sector`, `target_customers`, `sdg14_targets`)
   and code-derived facts are `inferred`. Base confidence comes from the source type; see
   `facts.py`.
6. **Derive** `website_domain`, `key_roles_missing`, `total_raised`, `stage` and `last_changed`.
7. **Score** with rule tables (`scoring.py`). TRL comes from `dev_stage`/`pilots`/`certifications`;
   BRL from `customer_validation`/`business_model`/`revenue_trend`; Ocean Impact Readiness (1–5) from
   section E. Each level lists its basis and the quotes behind it. Each of the 10 investment criteria
   gets a 1–5 score and a confidence, e.g. "Team 3/5, confidence low (2 of 4 fields found)". Weights
   are set in `config.toml`.
8. **Next steps** come from the gap rules in the schema, ordered weakest dimension first. Every null or
   low-confidence field with a question becomes an entry in `data_gaps`, which works as a question
   list for the fund's first call.

Pages and LLM responses are cached in `cache/`, so reruns cost nothing and demos are reproducible. Use
`--refresh` to re-fetch.

## Entry layout

```jsonc
{
  "schema_version": "1.0", "id": "sulapac-com", "name": "...", "website": "...", "generated_at": "...",
  "lead": { ... },                      // discovery info when the startup came from discover
  "sections": {
    "C": { "title": "Technology", "last_changed": "2026-10-17", "facts": {
      "dev_stage": { "field": "dev_stage", "value": "prototype_relevant_env",
                     "evidence": "…verbatim quote…", "source_url": "https://…", "source_type": "website",
                     "retrieved_at": "2026-10-17", "status": "claimed", "confidence": 0.7 },
      "pilots": [ { "field": "pilots", "value": { "partner": "Port of Turku", ... }, ... } ],
      "patents": null                   // null = unknown, not "no"
    } }
  },
  "scores": { "trl": { "level": 6, "basis": [...], "evidence": [...] }, "brl": ..., "ocean_impact_readiness": ...,
              "criteria": [ { "name": "Team", "score": 3, "confidence": 0.3, "fields_found": 2, "fields_total": 4, ... } ],
              "investment_score": 3.1, "overall_confidence": 0.42 },
  "next_steps": [ { "type": "Commercial validation: get a paid pilot", "reason": "...", "matched_to": "..." } ],
  "data_gaps":  [ { "field": "pricing", "question": "How is your offering priced?" } ],
  "sources": [...], "rejected_extractions": [...], "errors": [...]
}
```

`uv run startup-agent schema` prints the full JSON Schema.

## Shared vocabularies

`startup_agent/vocab.py` defines every enum used for scoring and matching: the 10 BlueInvest sectors,
stages, dev stages, customer validation, customer segments and more. The opportunity side (investors,
grants, partners) should use the same values, so matching becomes a join. `CUSTOMER_SEGMENTS` is a
proposed list; extend it as partner data arrives.

## Not done yet

- Opportunity matching. Next steps describe *which kind* of opportunity to match ("Grants whose TRL
  range covers TRL 4"). Named matches need the hand-curated investor/grant/partner data.
- Financial statements (revenue/profit/equity) are not in PRH's open API.
- Pitch-deck PDFs.

## Tests

```bash
uv run pytest                 # from Modules/Agent
```
