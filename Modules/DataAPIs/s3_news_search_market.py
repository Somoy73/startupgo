"""Sections 6-8: news/traction, web search & extraction, market sizing (+ GBIF)."""
from __future__ import annotations

import os
import time
import xml.etree.ElementTree as ET

from common import http, need, source


# ---------- 6 news & traction ----------
@source(name="hn_firebase", section="6 News & traction", access="free",
        endpoint="https://hacker-news.firebaseio.com/v0/{newstories|topstories|beststories|showstories|item/ID}.json", use="Stories and items",
        params={"list": "newstories | topstories | beststories | askstories | showstories | jobstories", "limit": "items to expand (extra)"},
        defaults={"list": "showstories", "limit": 5})
def hn_firebase(list="showstories", limit=5):
    ids = http(f"https://hacker-news.firebaseio.com/v0/{list}.json")[:limit]
    return [http(f"https://hacker-news.firebaseio.com/v0/item/{i}.json") for i in ids]


@source(name="hn_algolia", section="6 News & traction", access="free",
        endpoint="https://hn.algolia.com/api/v1/search", use="Show HN launches, points, comments (also /search_by_date)",
        params={"query": "", "tags": "story, show_hn, ask_hn, comment, author_X, story_ID", "numericFilters": "points>50,created_at_i>TS,num_comments>5",
                "page": "", "hitsPerPage": "<=1000", "restrictSearchableAttributes": "", "typoTolerance": ""},
        defaults={"query": "ocean", "tags": "show_hn", "numericFilters": "points>5", "hitsPerPage": 5})
def hn_algolia(**p):
    return http("https://hn.algolia.com/api/v1/search", p)


@source(name="product_hunt", section="6 News & traction", access="key",
        endpoint="https://api.producthunt.com/v2/api/graphql", use="Launches, votes, makers",
        params={"posts(first,after,postedAfter,postedBefore,order,topic,featured,twitterUrl,url)": "GraphQL args; order=VOTES|NEWEST|RANKING"},
        defaults={}, notes="env PRODUCTHUNT_TOKEN (OAuth bearer)")
def product_hunt(first=5, topic="artificial-intelligence"):
    q = "query($t:String){posts(first:%d,topic:$t,order:VOTES){edges{node{name tagline votesCount website createdAt}}}}" % first
    return http("https://api.producthunt.com/v2/api/graphql", method="POST",
                headers={"Authorization": f"Bearer {need('PRODUCTHUNT_TOKEN')}"}, json_body={"query": q, "variables": {"t": topic}})


@source(name="gdelt_doc", section="6 News & traction", access="free",
        endpoint="https://api.gdeltproject.org/api/v2/doc/doc", use="Global news mentions, tone",
        params={"query": "keywords, sourcecountry:, sourcelang:, domain:, theme:", "mode": "artlist|timelinevol|timelinetone|timelinelang|tonechart|wordcloud",
                "format": "json|csv|html|rss", "maxrecords": "<=250", "timespan": "e.g. 7d, 1month", "startdatetime": "YYYYMMDDHHMMSS",
                "enddatetime": "", "sort": "DateDesc|DateAsc|ToneDesc|ToneAsc|HybridRel"},
        defaults={"query": "\"ocean technology\"", "mode": "artlist", "format": "json", "maxrecords": 5, "timespan": "1week"},
        notes="One request per ~5 s.", slow=True)
def gdelt(**p):
    for wait in (6, 20, 45, 60):  # GDELT: max one request per 5 s, and it throttles shared IPs
        time.sleep(wait)
        try:
            d = http("https://api.gdeltproject.org/api/v2/doc/doc", p)
            if isinstance(d, str) and "limit requests" in d:  # throttle notice comes back as a 200 text body
                continue
            return d
        except RuntimeError as e:
            if "429" not in str(e):
                raise
    raise RuntimeError("HTTP 429 after retries (GDELT throttling this IP); retry later")


@source(name="google_news_rss", section="6 News & traction", access="free",
        endpoint="https://news.google.com/rss/search", use="Press coverage (unofficial RSS)",
        params={"q": "query, supports when:7d, site:, intitle:", "hl": "en-US", "gl": "US", "ceid": "US:en"},
        defaults={"q": "ocean startup funding when:30d", "limit": 5})
def google_news(q="ocean startup funding when:30d", hl="en-US", gl="US", ceid="US:en", limit=5):
    xml = http("https://news.google.com/rss/search", {"q": q, "hl": hl, "gl": gl, "ceid": ceid}, raw=True)
    return [{c.tag: c.text for c in it if c.tag in ("title", "link", "pubDate", "source")} for it in ET.fromstring(xml).iter("item")][:limit]


@source(name="newsapi", section="6 News & traction", access="key",
        endpoint="https://newsapi.org/v2/everything", use="News search (also /top-headlines)",
        params={"q": "", "qInTitle": "", "sources": "", "domains": "", "from": "ISO date", "to": "", "language": "", "sortBy": "relevancy|popularity|publishedAt",
                "pageSize": "<=100", "page": ""},
        defaults={"q": "ocean startup", "pageSize": 5}, notes="env NEWSAPI_KEY")
def newsapi(**p):
    return http("https://newsapi.org/v2/everything", p, headers={"X-Api-Key": need("NEWSAPI_KEY")})


@source(name="wayback_cdx", section="6 News & traction", access="free",
        endpoint="https://web.archive.org/cdx/search/cdx", use="Website history (pivots, growth)",
        params={"url": "page or domain (matchType=domain, url=*.x.com)", "output": "json", "from": "YYYY", "to": "YYYY", "limit": "",
                "filter": "statuscode:200, mimetype:text/html", "collapse": "timestamp:6 (one/month), digest", "fl": "timestamp,original,statuscode,digest,length",
                "matchType": "exact|prefix|host|domain"},
        defaults={"url": "saildrone.com", "output": "json", "limit": 5, "collapse": "timestamp:6", "filter": "statuscode:200"})
def wayback(**p):
    return http("https://web.archive.org/cdx/search/cdx", p)


@source(name="common_crawl_index", section="6 News & traction", access="free",
        endpoint="https://index.commoncrawl.org/{collection}-index", use="Locate crawled pages (WARC offsets) for bulk text",
        params={"url": "page or *.domain", "output": "json", "limit": "", "filter": "=status:200", "from": "", "to": "", "fl": "fields", "matchType": ""},
        defaults={"url": "oceana.org/about", "limit": 3})
def common_crawl(url="oceana.org/about", limit=3, collection=None, **extra):
    import json
    cols = [collection] if collection else [c["id"] for c in http("https://index.commoncrawl.org/collinfo.json")[:4]]
    err = None
    for col in cols:  # the newest index is sometimes overloaded (504); fall back to older ones
        try:
            txt = http(f"https://index.commoncrawl.org/{col}-index", {"url": url, "output": "json", "limit": limit, **extra}, raw=True)
            return {"collection": col, "records": [json.loads(l) for l in txt.splitlines() if l.startswith("{")]}
        except RuntimeError as e:
            err = e
    raise err


# ---------- 7 search & extraction ----------
@source(name="brave_search", section="7 Search & extraction", access="key",
        endpoint="https://api.search.brave.com/res/v1/web/search", use="Web search",
        params={"q": "", "country": "", "search_lang": "", "count": "<=20", "offset": "", "safesearch": "", "freshness": "pd|pw|pm|py|range", "result_filter": "", "extra_snippets": ""},
        defaults={"q": "ocean tech startups Finland", "count": 5}, notes="env BRAVE_API_KEY")
def brave(**p):
    return http("https://api.search.brave.com/res/v1/web/search", p, headers={"X-Subscription-Token": need("BRAVE_API_KEY")})


@source(name="tavily", section="7 Search & extraction", access="key", endpoint="https://api.tavily.com/search", use="AI search",
        params={"query": "", "search_depth": "basic|advanced", "topic": "general|news", "max_results": "", "days": "", "include_answer": "bool",
                "include_raw_content": "bool", "include_domains": "", "exclude_domains": ""},
        defaults={"query": "ocean tech startups Finland", "max_results": 5}, notes="env TAVILY_API_KEY")
def tavily(**p):
    return http("https://api.tavily.com/search", method="POST", json_body=p, headers={"Authorization": f"Bearer {need('TAVILY_API_KEY')}"})


@source(name="exa", section="7 Search & extraction", access="key", endpoint="https://api.exa.ai/search", use="AI search",
        params={"query": "", "type": "auto|neural|keyword", "numResults": "", "includeDomains": "", "excludeDomains": "", "startPublishedDate": "",
                "category": "company|news|research paper|...", "contents": "{text:true, highlights:true}"},
        defaults={"query": "ocean tech startups Finland", "numResults": 5}, notes="env EXA_API_KEY")
def exa(**p):
    return http("https://api.exa.ai/search", method="POST", json_body=p, headers={"x-api-key": need("EXA_API_KEY")})


@source(name="jina_reader", section="7 Search & extraction", access="free", endpoint="https://r.jina.ai/{url}",
        use="Any page → markdown (s.jina.ai/<query> for search)",
        params={"url": "target page", "headers X-Return-Format": "markdown|html|text", "X-Target-Selector": "css", "X-With-Links-Summary": "true"},
        defaults={"url": "https://www.saildrone.com"})
def jina(url="https://www.saildrone.com"):
    return {"url": url, "markdown": http(f"https://r.jina.ai/{url}", raw=True, headers={"Accept": "text/plain"})}


@source(name="firecrawl", section="7 Search & extraction", access="key", endpoint="https://api.firecrawl.dev/v1/scrape",
        use="Scrape/crawl (also /v1/crawl, /v1/map)", params={"url": "", "formats": "markdown,html,links,screenshot", "onlyMainContent": "bool", "waitFor": "ms"},
        defaults={"url": "https://www.saildrone.com"}, notes="env FIRECRAWL_API_KEY")
def firecrawl(**p):
    return http("https://api.firecrawl.dev/v1/scrape", method="POST", json_body=p, headers={"Authorization": f"Bearer {need('FIRECRAWL_API_KEY')}"})


# ---------- 8 market sizing ----------
@source(name="eurostat", section="8 Market sizing", access="free",
        endpoint="https://ec.europa.eu/eurostat/api/dissemination/statistics/1.0/data/{code}", use="EU statistics (e.g. fish_aq2a aquaculture, sbs_* business stats)",
        params={"code": "dataset code (path)", "geo": "FI, EU27_2020 ...", "time": "year (repeatable)", "sinceTimePeriod": "2015", "untilTimePeriod": "",
                "lang": "EN", "format": "JSON", "unit/…": "any dataset dimension as filter"},
        defaults={"code": "fish_aq2a", "geo": "FI", "lastTimePeriod": 1})
def eurostat(code="fish_aq2a", **p):
    d = http(f"https://ec.europa.eu/eurostat/api/dissemination/statistics/1.0/data/{code}", {"format": "JSON", "lang": "EN", **p})
    return {k: d[k] for k in ("label", "id", "size", "dimension", "value") if k in d} if isinstance(d, dict) else d


@source(name="oecd_sdmx", section="8 Market sizing", access="free",
        endpoint="https://sdmx.oecd.org/public/rest/data/{agency},{dataflow},{ver}/{key}", use="OECD indicators (e.g. ocean economy)",
        params={"startPeriod": "", "endPeriod": "", "dimensionAtObservation": "AllDimensions", "format": "jsondata|csvfilewithlabels", "lastNObservations": "", "detail": "full|dataonly"},
        defaults={"dataflow": "OECD.ENV.EPI,DSD_SOE@DF_SOE,1.0", "key": "all", "lastNObservations": 1},
        notes="Default = Sustainable Ocean Economy. Browse dataflows: GET https://sdmx.oecd.org/public/rest/dataflow/all/all/latest with Accept: application/vnd.sdmx.structure+json")
def oecd(dataflow="OECD.ENV.EPI,DSD_SOE@DF_SOE,1.0", key="all", **p):
    d = http(f"https://sdmx.oecd.org/public/rest/data/{dataflow}/{key}", {"format": "jsondata", **p})
    ds = d["data"]["dataSets"][0]
    key = "series" if "series" in ds else "observations"  # keep the payload small: 20 entries + structure
    ds[key] = dict(list(ds[key].items())[:20])
    return d


@source(name="world_bank", section="8 Market sizing", access="free",
        endpoint="https://api.worldbank.org/v2/country/{iso}/indicator/{code}", use="Macro indicators (also /country, /indicator, /topic, /source)",
        params={"format": "json", "date": "2015:2024", "per_page": "", "page": "", "mrv": "most recent N", "mrnev": "", "source": "db id", "gapfill": "Y"},
        defaults={"iso": "FIN", "code": "NY.GDP.MKTP.CD", "mrv": 5})
def world_bank(iso="FIN", code="NY.GDP.MKTP.CD", **p):
    return http(f"https://api.worldbank.org/v2/country/{iso}/indicator/{code}", {"format": "json", **p})


@source(name="statfin_pxweb", section="8 Market sizing", access="free",
        endpoint="https://pxdata.stat.fi/PXWeb/api/v1/en/{path}", use="Statistics Finland tables (GET = metadata, POST = data)",
        params={"query[]": "[{code,selection:{filter:item|all,values}}]", "response": '{"format":"json-stat2|csv|px"}'},
        defaults={"path": "StatFin/"}, notes="Sample lists the top-level database tree; POST a query to a table path for data.")
def statfin(path="StatFin/"):
    return http(f"https://pxdata.stat.fi/PXWeb/api/v1/en/{path}")


@source(name="gbif", section="8 Market sizing", access="free", endpoint="https://api.gbif.org/v1/occurrence/search",
        use="Species occurrences for impact claims (also /species, /dataset)",
        params={"q": "", "scientificName": "", "country": "ISO-2", "year": "range 2020,2025", "hasCoordinate": "bool", "basisOfRecord": "", "taxonKey": "",
                "geometry": "WKT", "limit": "<=300", "offset": "", "facet": ""},
        defaults={"scientificName": "Macrocystis pyrifera", "country": "US", "limit": 3})
def gbif(**p):
    d = http("https://api.gbif.org/v1/occurrence/search", p)
    return {"count": d["count"], "results": [{k: r.get(k) for k in ("key", "scientificName", "country", "year", "decimalLatitude", "decimalLongitude")} for r in d["results"]]}


@source(name="serpapi_google", section="7 Search & extraction", access="key", endpoint="https://serpapi.com/search?engine=google",
        use="Google web search: organic results + knowledge panel (founded, HQ, employees, founders)",
        params={"q": "", "num": "results", "start": "offset", "gl": "country", "hl": "language", "location": "", "tbs": "time filter e.g. qdr:m",
                "safe": "active|off", "device": "desktop|mobile"},
        defaults={"q": "Clearbot ocean cleanup", "num": 10}, notes="env SERPAPI_KEY; 1 search per call")
def serpapi_google(**p):
    return http("https://serpapi.com/search", {"engine": "google", **p, "api_key": need("SERPAPI_KEY")})


@source(name="serpapi_google_jobs", section="6 News & traction", access="key", endpoint="https://serpapi.com/search?engine=google_jobs",
        use="Job postings aggregated by Google (hiring signals)",
        params={"q": "", "location": "", "gl": "", "hl": "", "lrad": "radius km", "ltype": "1 = work from home", "uds": "filter token", "next_page_token": ""},
        defaults={"q": "Notpla"}, notes="env SERPAPI_KEY; 1 search per call")
def serpapi_google_jobs(**p):
    return http("https://serpapi.com/search", {"engine": "google_jobs", **p, "api_key": need("SERPAPI_KEY")})
