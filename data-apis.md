# Ocean Opportunity Radar – Data APIs




Access: **Free** = no sign-up · **Key** = free registration · **Paid** = commercial licence

## 1. Startup and investor data

| API | Access | Endpoint / how | Use |
|---|---|---|---|
| Crunchbase API v4 | Paid (free tier retired; enterprise licence, quote only) | `api.crunchbase.com/api/v4` | Companies, funding rounds, investors |
| Harmonic | Paid | Vendor API | Startup discovery, funding, team signals |
| YC OSS (unofficial) | Free | `yc-oss.github.io/api/...` (see Tested endpoints) | YC companies: batch, team size, hiring, tags |
| Dealroom API | Paid | Ask Dealroom or the organizers | EU startups, rounds |
| PitchBook API | Paid | Enterprise only | Deals, investors |
| Tracxn API | Paid | Enterprise only | Startup profiles |
| People Data Labs | Key (free tier) | Company Enrichment API | Headcount, industry, location |
| Wikidata SPARQL | Free | `query.wikidata.org/sparql` | Companies, VCs, founding dates, links |
| SEC EDGAR | Free (needs a User-Agent header) | `data.sec.gov` | US Form D filings (fundraises), investor filings |

## 2. Company registries and financials

| API | Access | Endpoint | Use |
|---|---|---|---|
| PRH / YTJ open data (Finland) | Free | `avoindata.prh.fi` (YTJ API v3) | Finnish business ID, industry, address, registration date |
| GLEIF LEI | Free | `api.gleif.org/api/v1` | Legal entities, parent/child companies |
| OpenCorporates | Key (free access is limited) | `api.opencorporates.com/v0.4` | Multi-country registry data |
| UK Companies House | Key (600 req / 5 min) | `api.company-information.service.gov.uk` | UK profile, officers, filing history, charges |
| Asiakastieto / Enento, Orbis | Paid (universities may have Orbis) | Vendor portals | Financial statements |

## 3. Funding and grants

| API | Access | Endpoint | Use |
|---|---|---|---|
| EU Funding & Tenders (SEDIA) | Free (`apiKey=SEDIA`) | `api.tech.ec.europa.eu/search-api/prod/rest/search` | Open EU calls, deadlines, topics |
| CORDIS (Horizon / EIC projects) | Free | Bulk CSV/JSON on `data.europa.eu`, plus the EURIO SPARQL endpoint | Who received EU funding, consortia, TRL |
| data.europa.eu | Free | `data.europa.eu/api/hub/search`, `data.europa.eu/sparql` | Finding EU datasets (FTS beneficiaries, EMFAF) |
| avoindata.fi (CKAN) | Free | `www.avoindata.fi/data/api/3/action/package_search` | Finnish open datasets; check for Business Finland funding decisions |
| Grants.gov | Free | REST search API | US grants |
| UKRI Gateway to Research | Free | `gtr.ukri.org` API | UK-funded projects and organisations |

## 4. Procurement (client demand signals)

| API | Access | Endpoint | Use |
|---|---|---|---|
| TED API v3 | Free (anonymous search) | `api.ted.europa.eu/v3/notices/search` | EU public buyers of ocean tech |
| Hilma (Finland) | Key | Hilma developer portal | Finnish public tenders |

## 5. Patents and research (TRL evidence)

| API | Access | Endpoint | Use |
|---|---|---|---|
| EPO Open Patent Services | Key (free quota) | `ops.epo.org/3.2/rest-services` | European patents |
| Google Patents (BigQuery) | Free tier | Dataset `patents-public-data` | Global patents, bulk SQL |
| PatentsView | Key | US patents only | US patents |
| Lens.org | Token on request | Lens API | Patents and papers combined |
| OpenAlex | Free | `api.openalex.org` | Papers, authors, institutions (research partners) |
| Semantic Scholar | Free (optional key) | `api.semanticscholar.org/graph/v1` | Papers, citations |
| Crossref | Free | `api.crossref.org` | Publication metadata |
| GitHub | Token | `api.github.com` | Open-source activity of tech teams |

## 6. News, launch and traction signals

| API | Access | Endpoint | Use |
|---|---|---|---|
| Hacker News (Firebase) | Free | `hacker-news.firebaseio.com/v0` | New stories, items |
| Hacker News (Algolia) | Free | `hn.algolia.com/api/v1/search` | Show HN launches, points, comments |
| Product Hunt v2 (GraphQL) | OAuth token; commercial use may need approval | `api.producthunt.com/v2/api/graphql` | Launches, votes, makers |
| GDELT DOC 2.0 | Free | `api.gdeltproject.org/api/v2/doc/doc` | Global news mentions, tone |
| Google News RSS | Free (unofficial) | `news.google.com/rss/search?q=...` | Press coverage |
| NewsAPI.org | Key (dev tier) | `newsapi.org/v2` | News search |
| Wayback Machine CDX | Free | `web.archive.org/cdx/search/cdx` | Website history (pivots, growth) |
| Common Crawl index | Free | `index.commoncrawl.org` | Bulk website text |

## 7. Web search and extraction (for an LLM agent)

| API | Access | Use |
|---|---|---|
| Brave Search API | Key (free tier) | Web search |
| Tavily / Exa | Key (free tiers) | AI-oriented search with clean results |
| Jina Reader | Free (`r.jina.ai/<url>`) | Any web page converted to markdown |
| Firecrawl | Key or self-host (open source) | Crawl whole sites to markdown |

## 8. Market sizing

| API | Access | Endpoint |
|---|---|---|
| Eurostat | Free | `ec.europa.eu/eurostat/api/dissemination/statistics/1.0/data/{code}` |
| OECD SDMX | Free | `sdmx.oecd.org/public/rest` |
| World Bank | Free | `api.worldbank.org/v2` |
| Statistics Finland (PxWeb) | Free | `pxdata.stat.fi/PXWeb/api/v1/en` |

Optional ocean data for checking impact claims: GBIF (`api.gbif.org/v1`), EMODnet (OGC map services) and the Copernicus Marine toolbox.

## 9. Tested endpoints (2026-10-16)

Each endpoint got one GET request (POST for Product Hunt) from the Deere network. The "Result" column shows what came back.

> **Corporate network:** `curl.exe` fails with `CRYPT_E_REVOCATION_OFFLINE`. Add `--ssl-no-revoke`, which skips the revocation check only; certificate validation still applies.

| API | Endpoint | Auth | Rate limit | Result |
|---|---|---|---|---|
| SEC EDGAR submissions | `https://data.sec.gov/submissions/CIK{10-digit-CIK}.json` | None; send a User-Agent with contact info | 10 req/s | 200 JSON |
| SEC full-text search (Form D) | `https://efts.sec.gov/LATEST/search-index?q="ocean"&forms=D` | Same | 10 req/s | 200 JSON (search hits) |
| SEC full index | `https://www.sec.gov/Archives/edgar/full-index/{year}/QTR{n}/` | Same | 10 req/s | 200 HTML listing |
| SEC company tickers | `https://www.sec.gov/files/company_tickers.json` | Same | 10 req/s | 200 JSON (public companies only) |
| UK Companies House | `https://api.company-information.service.gov.uk/search/companies?q=...` | Free key (HTTP Basic, key as username) | 600 req / 5 min | 401 without key, as expected |
| YC OSS | `https://yc-oss.github.io/api/meta.json` | None | GitHub Pages | 200; 6,307 companies |
| YC OSS | `.../companies/{all,top,hiring}.json` | None | GitHub Pages | 200; `all.json` is about 10.6 MB |
| YC OSS | `.../batches/{batch}.json` (e.g. `winter-2025`) | None | GitHub Pages | 200 |
| YC OSS | `.../industries/{industry}.json`, `.../tags/{tag}.json` | None | GitHub Pages | Listed in `meta.json` |
| GitHub search | `https://api.github.com/search/repositories?q=topic:ocean&sort=stars&per_page=..` | Token optional | Search: 10/min without a token (measured); 5,000/h core with a token | 200 JSON |
| HN Firebase | `https://hacker-news.firebaseio.com/v0/newstories.json`, `/v0/item/{id}.json` | None | Not documented | 200 JSON |
| HN Algolia | `https://hn.algolia.com/api/v1/search?query=...&tags=show_hn&numericFilters=points>50` | None | Not checked | 200 JSON |
| Product Hunt | `POST https://api.producthunt.com/v2/api/graphql` | OAuth token | Not checked | 401 `invalid_oauth_token` without a token, as expected |
| OpenCorporates | `https://api.opencorporates.com/v0.4/companies/search?q=...` | API key | Free access is limited | 401 without key, as expected |

### What each one returns

- **SEC Form D:** issuer name, industry group, total offering, amount sold, date of first sale, number of investors and related persons. Each filing has a `primary_doc.xml` with the structured data. Amendments are filed as `D/A`. CIKs are zero-padded to 10 digits.
- **YC OSS:** name, one_liner, batch, team_size, website, isHiring, industry and tags. Filter on the client side. It's unofficial and community-maintained.
- **GitHub:** stars, forks, contributors, commit velocity, open issues. Query with `q` (e.g. `topic:llm created:>2026-01-01`), `sort=stars`, `order`, `per_page`.
- **Hacker News:** launch posts (`tags=show_hn`), points, comments, dates.
- **Product Hunt:** votesCount, makers, website, launch date. Query `posts` with `postedAfter`, `order`, `topic`.
- **Companies House / OpenCorporates:** search by name, number, SIC code, incorporation date, status, jurisdiction.

### YC data for the blue economy is thin

`meta.json` has only a few relevant tags: `maritime` (3), `autonomous-shipping` (2), `climatetech` (32). Use YC as a comparison set, not as the main source of ocean startups.

## 10. Core fields to pull per startup

- **Identity:** name, domain, description, founded date, HQ
- **Category:** sector, tags, stage
- **Funding:** round amounts, dates, investors, total raised, valuation
- **Team:** headcount, founders, hiring status
- **Traction:** GitHub stars, Product Hunt votes, Hacker News points

Open sources are good for identity, filings and traction signals. They're weak on funding rounds, investors and valuations, which usually need a paid provider (Crunchbase, Harmonic, PitchBook, Dealroom) or SEC Form D for US raises.

## No public API: scrape or export instead

- EU BlueInvest, 1000 Ocean Startups, Ocean Impact Navigator
- Accelerator and VC portfolio pages (Katapult, Hatch, SOA, PortXL, FiBAN, Finnish VCs)
- Business Finland funding pages, and keep.eu (Interreg projects, which offers exports)
- LinkedIn: the official API is for approved partners only, so don't scrape it.

## Best free, no-sign-up set for a hackathon

SEDIA, CORDIS, TED, PRH/YTJ, GLEIF, OpenAlex, Wikidata and GDELT, plus Jina Reader for startup websites.
