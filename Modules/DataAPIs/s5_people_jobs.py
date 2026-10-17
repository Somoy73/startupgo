"""People (founders, executives, boards) and hiring sources."""
from __future__ import annotations

import re
from datetime import datetime, timezone

from common import http, need, source


@source(name="pdl_person_search", section="1 Startup & investor", access="key", endpoint="https://api.peopledatalabs.com/v5/person/search",
        use="People at a company (founders, executives, board) with career history and education; 1 credit per person returned",
        params={"sql": "PDL SQL over the person index, e.g. WHERE job_company_website='kelp.blue' AND job_title_levels='cxo'",
                "size": "persons to return (credits)", "scroll_token": "paging", "dataset": "all | resume | email ...",
                "titlecase": "bool", "data_include": "comma list of fields to return"},
        defaults={}, notes="env PDL_API_KEY. Results include contact data; ingest_gaps.py never stores emails, phones or sex.")
def pdl_person_search(sql: str, size: int = 5):
    return http("https://api.peopledatalabs.com/v5/person/search", method="POST", json_body={"sql": sql, "size": size},
                headers={"X-Api-Key": need("PDL_API_KEY")})


def _ts(v):
    if isinstance(v, (int, float)):  # epoch ms (Lever)
        return datetime.fromtimestamp(v / 1000, timezone.utc).date().isoformat()
    return (v or "")[:10] or None


@source(name="job_boards", section="6 News & traction", access="free",
        endpoint="Public job-board APIs: Ashby, Greenhouse, Lever, Workable, Recruitee, Personio",
        use="Open roles straight from a company's applicant-tracking system (no key)",
        params={"ats": "ashby | greenhouse | lever | workable | recruitee | personio", "slug": "the company's board name, e.g. sofarocean"},
        defaults={"ats": "ashby", "slug": "sofarocean"})
def job_boards(ats="ashby", slug="sofarocean"):
    """Return a normalised list: [{title, location, department, url, posted}]."""
    if ats == "ashby":
        d = http(f"https://api.ashbyhq.com/posting-api/job-board/{slug}")
        return [{"title": j.get("title"), "location": j.get("location"), "department": j.get("department"), "url": j.get("jobUrl"),
                 "posted": _ts(j.get("publishedAt"))} for j in d.get("jobs", [])]
    if ats == "greenhouse":
        d = http(f"https://boards-api.greenhouse.io/v1/boards/{slug}/jobs", {"content": "true"})
        return [{"title": j.get("title"), "location": (j.get("location") or {}).get("name"),
                 "department": ", ".join(x.get("name", "") for x in j.get("departments") or []), "url": j.get("absolute_url"),
                 "posted": _ts(j.get("updated_at"))} for j in d.get("jobs", [])]
    if ats == "lever":
        d = http(f"https://api.lever.co/v0/postings/{slug}", {"mode": "json"})
        return [{"title": j.get("text"), "location": (j.get("categories") or {}).get("location"), "department": (j.get("categories") or {}).get("team"),
                 "url": j.get("hostedUrl"), "posted": _ts(j.get("createdAt"))} for j in d]
    if ats == "workable":
        d = http(f"https://apply.workable.com/api/v1/widget/accounts/{slug}")
        return [{"title": j.get("title"), "location": ", ".join(x for x in (j.get("city"), j.get("country")) if x), "department": j.get("department"),
                 "url": j.get("url"), "posted": _ts(j.get("published_on"))} for j in d.get("jobs", [])]
    if ats == "recruitee":
        d = http(f"https://{slug}.recruitee.com/api/offers/")
        return [{"title": j.get("title"), "location": j.get("location"), "department": j.get("department"), "url": j.get("careers_url"),
                 "posted": _ts(j.get("published_at"))} for j in d.get("offers", [])]
    if ats == "personio":
        x = http(f"https://{slug}.jobs.personio.de/xml", raw=True)
        out = []
        for pos in re.findall(r"<position>(.*?)</position>", x, re.S):
            g = lambda t: (re.findall(fr"<{t}>(?:<!\[CDATA\[)?(.*?)(?:\]\]>)?</{t}>", pos, re.S) or [None])[0]  # noqa: E731
            out.append({"title": g("name"), "location": g("office"), "department": g("department"),
                        "url": f"https://{slug}.jobs.personio.de/job/{g('id')}", "posted": _ts(g("createdAt"))})
        return out
    raise ValueError(f"unknown ats {ats}")
