"""Sections 3-5: funding & grants, procurement, patents & research."""
from __future__ import annotations

import json
import time

from common import http, need, source


# ---------- 3 funding ----------
@source(name="eu_sedia_calls", section="3 Funding & grants", access="free",
        endpoint="https://api.tech.ec.europa.eu/search-api/prod/rest/search", use="Open EU calls, deadlines, topics",
        params={"apiKey": "SEDIA (fixed)", "text": "search text (use *)", "pageSize": "", "pageNumber": "",
                "query (multipart JSON body)": "bool/must filters e.g. type=[1,2] (calls), status=[31094501 forthcoming,31094502 open,31094503 closed]",
                "languages (multipart body)": '["en"]', "sort (multipart body)": '{"field":"deadlineDate","order":"ASC"}'},
        defaults={"text": "ocean", "pageSize": 5})
def sedia(text="ocean", pageSize=5, pageNumber=1, status=("31094501", "31094502")):
    q = {"bool": {"must": [{"terms": {"type": ["1", "2", "8"]}}, {"terms": {"status": list(status)}}]}}
    return http("https://api.tech.ec.europa.eu/search-api/prod/rest/search",
                {"apiKey": "SEDIA", "text": text, "pageSize": pageSize, "pageNumber": pageNumber},
                method="POST", multipart={"query": json.dumps(q), "languages": '["en"]'})


@source(name="cordis_via_data_europa", section="3 Funding & grants", access="free",
        endpoint="https://data.europa.eu/api/hub/search/search", use="Find CORDIS / EU funding datasets (bulk CSV/JSON, EURIO SPARQL)",
        params={"q": "text", "filter": "dataset|catalogue", "limit": "", "page": "0-based", "sort": "relevance+desc",
                "facets": "JSON", "aggregation": "", "minScore": ""},
        defaults={"q": "cordis horizon projects", "filter": "dataset", "limit": 5},
        notes="Real CORDIS project rows are in bulk downloads listed under each dataset's distributions.")
def cordis(**p):
    return http("https://data.europa.eu/api/hub/search/search", p)


@source(name="data_europa_search", section="3 Funding & grants", access="free",
        endpoint="https://data.europa.eu/api/hub/search/search", use="Find EU datasets (FTS beneficiaries, EMFAF)",
        params={"q": "text", "filter": "dataset", "limit": "", "page": "", "sort": "", "facets": ""},
        defaults={"q": "EMFAF beneficiaries", "filter": "dataset", "limit": 5})
def data_europa(**p):
    return http("https://data.europa.eu/api/hub/search/search", p)


@source(name="avoindata_fi_ckan", section="3 Funding & grants", access="free",
        endpoint="https://www.avoindata.fi/data/api/3/action/package_search", use="Finnish open datasets (Business Finland funding decisions)",
        params={"q": "solr query", "fq": "filter query", "sort": "", "rows": "<=1000", "start": "offset", "facet.field": "", "include_private": ""},
        defaults={"q": "Business Finland", "rows": 5})
def avoindata(**p):
    return http("https://www.avoindata.fi/data/api/3/action/package_search", p)


@source(name="grants_gov", section="3 Funding & grants", access="free",
        endpoint="https://api.grants.gov/v1/api/search2", use="US grant opportunities",
        params={"keyword": "", "rows": "", "startRecordNum": "", "oppStatuses": "forecasted|posted|closed|archived",
                "fundingCategories": "", "agencies": "", "eligibilities": "", "cfda": "", "sortBy": ""},
        defaults={"keyword": "ocean", "rows": 5, "oppStatuses": "forecasted|posted"})
def grants_gov(**p):
    return http("https://api.grants.gov/v1/api/search2", method="POST", json_body=p)


@source(name="ukri_gateway_to_research", section="3 Funding & grants", access="free",
        endpoint="https://gtr.ukri.org/gtr/api/projects", use="UK-funded projects and organisations",
        params={"q": "text", "s": "page size 10-100", "p": "page", "f": "field e.g. pro.t", "sf": "sort field", "so": "A|D",
                "(other paths)": "/organisations, /persons, /funds, /outcomes/publications"},
        defaults={"q": "ocean", "s": 10})
def ukri(**p):
    return http("https://gtr.ukri.org/gtr/api/projects", p, headers={"Accept": "application/vnd.rcuk.gtr.json-v7"})


# ---------- 4 procurement ----------
@source(name="ted_eu_tenders", section="4 Procurement", access="free",
        endpoint="https://api.ted.europa.eu/v3/notices/search", use="EU public buyers of ocean tech",
        params={"query": "expert query e.g. FT~ocean AND publication-date>=20260101", "fields": "list e.g. notice-title, buyer-name, publication-date",
                "page": "1-based", "limit": "<=250", "scope": "ALL|LATEST|ACTIVE", "paginationMode": "PAGE_NUMBER|ITERATION",
                "iterationNextToken": "", "onlyLatestVersions": "bool"},
        defaults={"query": "FT~ocean", "limit": 5})
def ted(query="FT~ocean", limit=5, page=1, fields=None, **extra):
    fields = fields or ["notice-title", "buyer-name", "publication-date", "notice-type", "publication-number"]
    return http("https://api.ted.europa.eu/v3/notices/search", method="POST",
                json_body={"query": query, "fields": fields, "limit": limit, "page": page, **extra})


@source(name="hilma_finland", section="4 Procurement", access="key", endpoint="Hilma developer portal",
        use="Finnish public tenders (stub)", params={}, defaults={}, notes="Subscription key from hilma.fi developer portal (env HILMA_KEY)")
def hilma(**p):
    need("HILMA_KEY")
    raise NotImplementedError("fill in subscription endpoint from portal after registration")


# ---------- 5 patents & research ----------
@source(name="epo_ops", section="5 Patents & research", access="key",
        endpoint="https://ops.epo.org/3.2/rest-services/published-data/search", use="European patents",
        params={"q": "CQL e.g. txt=ocean AND pd>=2025", "Range": "header 1-100"}, defaults={"q": "txt=kelp"},
        notes="env EPO_KEY + EPO_SECRET (OAuth client credentials)")
def epo(q="txt=kelp", rng="1-5"):
    tok = http("https://ops.epo.org/3.2/auth/accesstoken", method="POST", form={"grant_type": "client_credentials"},
               auth=(need("EPO_KEY"), need("EPO_SECRET")))["access_token"]
    return http("https://ops.epo.org/3.2/rest-services/published-data/search", {"q": q},
                headers={"Authorization": f"Bearer {tok}", "Range": f"{rng}", "Accept": "application/json"})


@source(name="google_patents_bigquery", section="5 Patents & research", access="free",
        endpoint="BigQuery: patents-public-data.patents.publications", use="Global patents, bulk SQL",
        params={"sql": "standard SQL"}, defaults={}, notes="Needs a GCP project + google-cloud-bigquery; not callable via plain HTTP here.")
def gpatents(**p):
    need("GOOGLE_APPLICATION_CREDENTIALS")
    raise NotImplementedError("pip install google-cloud-bigquery and run SQL against patents-public-data")


@source(name="patentsview", section="5 Patents & research", access="key",
        endpoint="https://search.patentsview.org/api/v1/patent/", use="US patents",
        params={"q": "JSON query", "f": "fields list", "o": "options {size,page}", "s": "sort"},
        defaults={"q": {"_text_any": {"patent_title": "ocean"}}}, notes="env PATENTSVIEW_KEY (X-Api-Key)")
def patentsview(q=None, size=5):
    return http("https://search.patentsview.org/api/v1/patent/",
                {"q": json.dumps(q or {"_text_any": {"patent_title": "ocean"}}), "o": json.dumps({"size": size}),
                 "f": json.dumps(["patent_id", "patent_title", "patent_date"])},
                headers={"X-Api-Key": need("PATENTSVIEW_KEY")})


@source(name="lens_org", section="5 Patents & research", access="key",
        endpoint="https://api.lens.org/patent/search", use="Patents and papers (also /scholarly/search)",
        params={"query": "ES query DSL", "size": "", "from": "", "include": "fields", "sort": "", "scroll": ""},
        defaults={}, notes="env LENS_TOKEN (Bearer)")
def lens(size=5):
    return http("https://api.lens.org/patent/search", method="POST", headers={"Authorization": f"Bearer {need('LENS_TOKEN')}"},
                json_body={"query": {"match": {"title": "ocean"}}, "size": size})


@source(name="openalex", section="5 Patents & research", access="free",
        endpoint="https://api.openalex.org/works", use="Papers, authors, institutions (also /authors, /institutions, /concepts, /funders)",
        params={"search": "full text", "filter": "e.g. publication_year:2025,type:article", "sort": "cited_by_count:desc",
                "per-page": "<=200", "page": "", "cursor": "*", "select": "fields", "group_by": "facet", "sample": "N", "mailto": "polite pool"},
        defaults={"search": "kelp aquaculture", "per-page": 5, "select": "id,title,publication_year,cited_by_count,authorships"})
def openalex(**p):
    return http("https://api.openalex.org/works", p)


@source(name="semantic_scholar", section="5 Patents & research", access="free",
        endpoint="https://api.semanticscholar.org/graph/v1/paper/search", use="Papers, citations",
        params={"query": "", "fields": "title,year,citationCount,authors,abstract,venue,openAccessPdf,externalIds,fieldsOfStudy",
                "year": "2020-2026", "venue": "", "fieldsOfStudy": "", "minCitationCount": "", "openAccessPdf": "flag",
                "offset": "", "limit": "<=100"},
        defaults={"query": "underwater robotics", "fields": "title,year,citationCount,venue", "limit": 5},
        notes="Heavily rate-limited without a key (env S2_API_KEY → x-api-key).", slow=True)
def s2(**p):
    import os
    h = {"x-api-key": os.environ["S2_API_KEY"]} if os.environ.get("S2_API_KEY") else {}
    for wait in (0, 8, 20):  # unauthenticated pool is shared and often 429s
        time.sleep(wait)
        try:
            return http("https://api.semanticscholar.org/graph/v1/paper/search", p, headers=h)
        except RuntimeError as e:
            if "429" not in str(e):
                raise
    raise RuntimeError("HTTP 429 after retries; set S2_API_KEY")


@source(name="crossref", section="5 Patents & research", access="free",
        endpoint="https://api.crossref.org/works", use="Publication metadata",
        params={"query": "", "query.title": "", "query.author": "", "filter": "from-pub-date:2025,type:journal-article",
                "rows": "<=1000", "offset": "", "cursor": "*", "sort": "relevance|published|is-referenced-by-count", "order": "asc|desc",
                "select": "fields", "mailto": "polite pool"},
        defaults={"query": "marine robotics", "rows": 5, "select": "DOI,title,issued,is-referenced-by-count,container-title"})
def crossref(**p):
    return http("https://api.crossref.org/works", p)


@source(name="github_search_repos", section="5 Patents & research", access="key",
        endpoint="https://api.github.com/search/repositories", use="Open-source activity (token optional; 10 searches/min without)",
        params={"q": "e.g. topic:ocean created:>2026-01-01 language:python stars:>10", "sort": "stars|forks|updated|help-wanted-issues",
                "order": "desc|asc", "per_page": "<=100", "page": ""},
        defaults={"q": "topic:ocean", "sort": "stars", "per_page": 5}, notes="optional env GITHUB_TOKEN")
def github(**p):
    import os
    h = {"Authorization": f"Bearer {os.environ['GITHUB_TOKEN']}"} if os.environ.get("GITHUB_TOKEN") else {}
    return http("https://api.github.com/search/repositories", p, headers=h)


@source(name="google_patents_xhr", section="5 Patents & research", access="free",
        endpoint="https://patents.google.com/xhr/query", use="Patent search with no key (unofficial web endpoint behind patents.google.com)",
        params={"q": "search terms (supports inventor:, assignee:, CPC codes)", "num": "results per page, max 100", "page": "0-based",
                "country": "US,EP,WO,CN ...", "before": "priority:20261231", "after": "priority:20200101", "status": "GRANT|APPLICATION",
                "type": "PATENT|DESIGN", "language": "ENGLISH", "sort": "new|old", "assignee": "", "inventor": ""},
        defaults={"q": "kelp", "num": 5},
        notes="Unofficial: it can change or block heavy use. Filters go inside the inner `url` query string, the wrapper builds it.")
def google_patents_xhr(q="kelp", num=5, page=0, **filters):
    import urllib.parse
    inner = urllib.parse.urlencode({"q": q, "num": num, "page": page, **filters})
    d = http("https://patents.google.com/xhr/query", {"url": inner, "exp": ""})
    res = d["results"]
    rows = [r["patent"] for c in res.get("cluster", []) for r in c.get("result", [])]
    keep = ("publication_number", "title", "snippet", "assignee", "inventor", "priority_date", "filing_date", "publication_date", "grant_date")
    return {"total": res["total_num_results"], "patents": [{k: p.get(k) for k in keep} for p in rows]}


@source(name="serpapi_google_patents", section="5 Patents & research", access="key",
        endpoint="https://serpapi.com/search?engine=google_patents", use="Google Patents search via SerpApi (stable, paid quota)",
        params={"q": "query", "page": "1-based", "num": "10-100", "sort": "new|old", "before": "priority:YYYYMMDD / filing: / publication:",
                "after": "same format", "inventor": "comma list", "assignee": "comma list", "country": "US,EP,WO ...", "language": "ENGLISH ...",
                "status": "GRANT|APPLICATION", "type": "PATENT|DESIGN", "litigation": "YES|NO", "dups": "language|family", "patents": "true|false (include patents)", "scholar": "true|false"},
        defaults={"q": "kelp", "num": 10}, notes="env SERPAPI_KEY")
def serpapi_patents(**p):
    return http("https://serpapi.com/search", {"engine": "google_patents", **p, "api_key": need("SERPAPI_KEY")})
