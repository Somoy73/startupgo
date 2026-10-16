# StartupGo Agent

Builds a startup entry that follows the **Ocean Opportunity Radar extraction schema**:
about 60 facts in 10 sections (A–J). Each fact carries evidence: a verbatim quote, its source URL, the
source type, the date it was read, a claimed/verified/inferred status and a confidence. TRL, BRL, Ocean
Impact Readiness, the 10 investment criteria, next steps and first-call questions are then **computed
by code from those facts**. The LLM extracts facts; it never scores.

This module is the agent interface. Page fetching and startup discovery (including Wellfound) live in
the separate `Modules/Scraper` package, which this module depends on.

## Setup

```bash
cd Modules/Agent
uv sync                       # creates .venv, installs ../Scraper as an editable dependency
cp .env.example .env          # add GEMINI_API_KEY (or the key named in config.toml)
```

## Usage

```bash
# One startup from its name and website → output/startups/<domain>.json
uv run startup-agent profile --name "Sulapac" --website https://www.sulapac.com

# Known Finnish business ID, plus extra independent sources (press release, CORDIS record, ...)
uv run startup-agent profile --name "Sulapac" --website sulapac.com \
    --business-id 2739393-2 --url https://example-news.fi/sulapac-raises

# Discover startups on a Wellfound collection page; add --profile to build entries for each
uv run startup-agent discover --url https://wellfound.com/startups/industry/clean-technology --limit 5
uv run startup-agent discover --url https://wellfound.com/startups/industry/clean-technology --limit 5 --profile

# Recompute scores/next steps after hand-correcting facts in an entry
uv run startup-agent rescore output/startups/sulapac-com.json

# JSON Schema of an entry, for other teams/services
uv run startup-agent schema --output startup_entry.schema.json

# LangGraph pipeline: research one startup, then evaluate and rank it
uv run startup-agent graph --mode both \
    --name "Sulapac" --website https://www.sulapac.com

# LangGraph research from a public discovery source
uv run startup-agent graph --mode research \
    --source wellfound \
    --url https://wellfound.com/startups/industry/clean-technology \
    --limit 5

# LangGraph evaluation of entries already saved as JSON
uv run startup-agent graph --mode evaluation \
    --entry output/startups/sulapac-com.json
```

The `graph` command is the multi-agent interface. The research node uses the existing public
scraper, crawler, source classification, registry connector, and evidence-backed section extractor.
The evaluation node reconstructs each saved record and recomputes TRL, BRL, Ocean Impact Readiness,
investment criteria, confidence, data gaps, and next steps. Use `--mode research` to stop after
research, `--mode evaluation` to evaluate existing `--entry` files, or `--mode both` (the default)
to run both nodes. Sources remain subject to robots.txt and normal public-access restrictions; the
workflow does not bypass login pages, CAPTCHAs, or access controls.

From Python:

```python
from pathlib import Path
from startup_agent import AgentSettings, build_agent

settings = AgentSettings.load(Path("config.toml"))
agent, fetcher = build_agent(settings)
try:
    record = agent.profile(name="Sulapac", website="https://www.sulapac.com")
    entry = record.to_dict(weights=settings.weights)
finally:
    fetcher.close()
```

## How it works

1. **Collect sources.** Crawl the homepage and up to `max_pages` same-site pages, picked by how well
   their URL matches each section's keywords (`/team`, `/technology`, `/impact`, `/news`, ...).
   `robots.txt` is respected. Extra `--url` pages are typed by domain: CORDIS → `eu_projects`,
   patent sites → `patent`, other domains → `news`. Discovery listings (Wellfound) count as the
   startup's own `website` claims.
2. **Structured data first.** For Finnish companies (`.fi` site, Finland found in section A, or
   `--business-id`), section A comes from the PRH open data API. These facts are `verified` with
   confidence 0.95, and override weaker website claims.
3. **One LLM call per section**, sending only that section's pages and a strict JSON schema (enums for
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
- Business Finland and CORDIS connectors. Pass their pages with `--url` for now.
- Financial statements (revenue/profit/equity) are not in PRH's open API.
- Pitch-deck PDFs.

## Tests

```bash
uv run pytest
```
