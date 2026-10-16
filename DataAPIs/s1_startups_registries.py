"""Sections 1-2: startup/investor data and company registries."""
from __future__ import annotations

import os

from common import http, need, source

SEC_UA = os.environ.get("SEC_USER_AGENT", "OceanOpportunityRadar mayajshetty@gmail.com")
YC = "https://yc-oss.github.io/api"


@source(name="yc_oss_meta", section="1 Startup & investor", access="free",
        endpoint=f"{YC}/meta.json", use="Counts and slugs for every YC batch / industry / tag",
        params={}, defaults={})
def yc_meta():
    return http(f"{YC}/meta.json")


@source(name="yc_oss_companies", section="1 Startup & investor", access="free",
        endpoint=f"{YC}/{{companies|batches|industries|tags}}/{{name}}.json",
        use="YC companies: batch, team size, hiring, tags (filtering is client-side)",
        params={"kind": "companies | batches | industries | tags",
                "name": "all | top | hiring  (companies);  e.g. winter-2025 (batches);  industry/tag slug from meta.json",
                "match": "client-side substring filter on name/one_liner/tags (extra)"},
        defaults={"kind": "tags", "name": "climatetech"},
        notes="companies/all.json is ~10 MB; the runner keeps only a 5-row sample on disk.")
def yc_companies(kind="tags", name="climatetech", match=None):
    d = http(f"{YC}/{kind}/{name}.json")
    if match and isinstance(d, list):
        m = match.lower()
        d = [c for c in d if m in (str(c.get("name", "")) + str(c.get("one_liner", "")) + str(c.get("tags", ""))).lower()]
    return d


@source(name="people_data_labs", section="1 Startup & investor", access="key",
        endpoint="https://api.peopledatalabs.com/v5/company/enrich", use="Headcount, industry, location",
        params={"website": "company domain", "name": "company name", "profile": "linkedin url",
                "ticker": "stock ticker", "pretty": "bool", "min_likelihood": "1-10", "titlecase": "bool"},
        defaults={"website": "saildrone.com"}, notes="env PDL_API_KEY")
def pdl(**p):
    return http("https://api.peopledatalabs.com/v5/company/enrich", p, headers={"X-Api-Key": need("PDL_API_KEY")})


@source(name="wikidata_sparql", section="1 Startup & investor", access="free",
        endpoint="https://query.wikidata.org/sparql", use="Companies, VCs, founding dates, websites",
        params={"query": "SPARQL text", "format": "json | xml | csv"},
        defaults={"search": "ocean"},
        notes="The wrapper builds an EntitySearch query from `search`; pass `query=` for your own SPARQL.")
def wikidata(search="ocean", query=None, limit=10):
    q = query or f"""
SELECT ?item ?itemLabel ?itemDescription ?inception ?website WHERE {{
  SERVICE wikibase:mwapi {{
    bd:serviceParam wikibase:endpoint "www.wikidata.org"; wikibase:api "EntitySearch";
    mwapi:search "{search}"; mwapi:language "en".
    ?item wikibase:apiOutputItem mwapi:item. }}
  OPTIONAL {{ ?item wdt:P571 ?inception }} OPTIONAL {{ ?item wdt:P856 ?website }}
  SERVICE wikibase:label {{ bd:serviceParam wikibase:language "en". }}
}} LIMIT {limit}"""
    return http("https://query.wikidata.org/sparql", {"query": q, "format": "json"})


@source(name="sec_edgar_submissions", section="1 Startup & investor", access="free",
        endpoint="https://data.sec.gov/submissions/CIK{cik10}.json", use="Filing history for one filer (CIK zero-padded to 10)",
        params={"cik": "int or str, padded to 10 digits"}, defaults={"cik": 1318605},
        notes="Needs User-Agent with contact (env SEC_USER_AGENT). 10 req/s.")
def sec_submissions(cik=1318605):
    return http(f"https://data.sec.gov/submissions/CIK{int(cik):010d}.json", headers={"User-Agent": SEC_UA})


@source(name="sec_edgar_fulltext_formD", section="1 Startup & investor", access="free",
        endpoint="https://efts.sec.gov/LATEST/search-index", use="Full-text search of filings, e.g. Form D fundraises",
        params={"q": "query, quote for phrases", "forms": "D, D/A, 10-K ...", "dateRange": "custom|1y|30d ...",
                "startdt": "YYYY-MM-DD", "enddt": "YYYY-MM-DD", "ciks": "CIK list", "from": "offset", "size": "page size"},
        defaults={"q": '"ocean"', "forms": "D"})
def sec_fulltext(**p):
    return http("https://efts.sec.gov/LATEST/search-index", p, headers={"User-Agent": SEC_UA})


@source(name="sec_company_tickers", section="1 Startup & investor", access="free",
        endpoint="https://www.sec.gov/files/company_tickers.json", use="Public company CIK/ticker map",
        params={}, defaults={})
def sec_tickers():
    d = http("https://www.sec.gov/files/company_tickers.json", headers={"User-Agent": SEC_UA})
    return dict(list(d.items())[:25]) if isinstance(d, dict) else d


@source(name="crunchbase_v4", section="1 Startup & investor", access="paid",
        endpoint="https://api.crunchbase.com/api/v4/searches/organizations", use="Companies, rounds, investors",
        params={"field_ids": "list", "query": "list of filters", "order": "sort", "limit": "<=1000", "after_id": "paging"},
        defaults={}, notes="Enterprise licence. env CRUNCHBASE_KEY (X-cb-user-key).")
def crunchbase(limit=5):
    return http("https://api.crunchbase.com/api/v4/searches/organizations", method="POST",
                headers={"X-cb-user-key": need("CRUNCHBASE_KEY")},
                json_body={"field_ids": ["identifier", "short_description", "funding_total"], "limit": limit,
                           "query": [{"type": "predicate", "field_id": "facet_ids", "operator_id": "includes", "values": ["company"]}]})


for _n, _e in [("harmonic", "https://api.harmonic.ai"), ("dealroom", "https://api.dealroom.co/api/v1"),
               ("pitchbook", "https://api.pitchbook.com"), ("tracxn", "https://platform.tracxn.com/api")]:
    def _mk(n=_n, e=_e):
        def f(**p):
            need(f"{n.upper()}_API_KEY")
            raise NotImplementedError(f"{n}: vendor contract/schema required; add request here once you have credentials")
        return f
    source(name=_n, section="1 Startup & investor", access="paid", endpoint=_e, use="Paid vendor (stub)",
           params={}, defaults={}, notes=f"env {_n.upper()}_API_KEY; stub only, no public docs")(_mk())


# ---------- 2 registries ----------
@source(name="prh_ytj_finland", section="2 Registries", access="free",
        endpoint="https://avoindata.prh.fi/opendata-ytj-api/v3/companies", use="Finnish business ID, industry, address, registration date",
        params={"name": "company name", "location": "town", "businessId": "e.g. 0112038-9", "companyForm": "OY, KY...",
                "mainBusinessLine": "TOL code", "registrationDateStart": "YYYY-MM-DD", "registrationDateEnd": "YYYY-MM-DD",
                "postCode": "", "businessLineCode": "", "page": "1-based"},
        defaults={"name": "wärtsilä"})
def prh(**p):
    return http("https://avoindata.prh.fi/opendata-ytj-api/v3/companies", p)


@source(name="gleif_lei", section="2 Registries", access="free",
        endpoint="https://api.gleif.org/api/v1/lei-records", use="Legal entities, parent/child links",
        params={"filter[fulltext]": "name search", "filter[entity.legalName]": "exact", "filter[lei]": "",
                "filter[entity.legalAddress.country]": "ISO-2", "filter[entity.category]": "", "page[number]": "", "page[size]": "<=200", "sort": ""},
        defaults={"filter[fulltext]": "wartsila", "page[size]": 3})
def gleif(**p):
    return http("https://api.gleif.org/api/v1/lei-records", p, headers={"Accept": "application/vnd.api+json"})


@source(name="opencorporates", section="2 Registries", access="key",
        endpoint="https://api.opencorporates.com/v0.4/companies/search", use="Multi-country registry data",
        params={"q": "name", "jurisdiction_code": "fi, gb, us_de ...", "country_code": "", "current_status": "", "incorporation_date": "from:to",
                "per_page": "<=100", "page": "", "order": "score|incorporation_date", "industry_codes": ""},
        defaults={"q": "ocean robotics"}, notes="env OPENCORPORATES_API_KEY")
def opencorporates(**p):
    return http("https://api.opencorporates.com/v0.4/companies/search", {**p, "api_token": need("OPENCORPORATES_API_KEY")})


@source(name="uk_companies_house", section="2 Registries", access="key",
        endpoint="https://api.company-information.service.gov.uk/search/companies", use="UK profile, officers, filings, charges",
        params={"q": "search text", "items_per_page": "<=100", "start_index": "offset",
                "(other paths)": "/company/{no}, /company/{no}/officers, /company/{no}/filing-history, /company/{no}/charges"},
        defaults={"q": "ocean", "items_per_page": 5}, notes="env COMPANIES_HOUSE_KEY (HTTP Basic user)")
def companies_house(**p):
    return http("https://api.company-information.service.gov.uk/search/companies", p, auth=(need("COMPANIES_HOUSE_KEY"), ""))


@source(name="orbis_asiakastieto", section="2 Registries", access="paid", endpoint="vendor portal", use="Financial statements (stub)",
        params={}, defaults={}, notes="No public API")
def orbis(**p):
    need("ORBIS_API_KEY")
    raise NotImplementedError("vendor contract required")
