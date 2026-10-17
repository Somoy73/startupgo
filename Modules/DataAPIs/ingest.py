#!/usr/bin/env python3
"""Load scraped API data into the Startup Go database and compute parameter gaps.

  python3 ingest.py               targeted per-startup pulls + funding/market pulls + gap analysis
  python3 ingest.py --gaps-only   only rebuild assessment_parameters / startup_parameter_status / GAPS.md
  python3 ingest.py --gaps-only --serpapi   only the SerpApi enrichment (2 searches per startup) + gaps
  python3 ingest.py --gaps-only --pdl   only People Data Labs (1 credit per matched startup) + gaps
  python3 ingest.py --gaps-only --uk   only the Companies House pull for UK startups + gaps
  python3 ingest.py --gdelt       also query GDELT per startup (slow: >= 6 s per call)

Writes to the runtime DB, DB/runtime/startupgo.db (or $STARTUPGO_DB), never to the tracked snapshot
DB/startupgo.db. A missing runtime DB is copied from the snapshot (or built from DB/schema.sql + DB/seed.sql),
and schema.sql (all IF NOT EXISTS) is re-applied so an existing DB gets new tables. `refresh.py snapshot`
copies the runtime DB back to the snapshot when you want to commit data.
Curated startups.* columns are never overwritten: new values go to field_suggestions.
"""
from __future__ import annotations

import json
import os
import re
import sqlite3
import sys
import time
from datetime import datetime, timezone
from pathlib import Path
from urllib.parse import urlparse

HERE = Path(__file__).parent
sys.path.insert(0, str(HERE))
import common  # noqa: E402
import s1_startups_registries, s2_funding_procurement_patents, s3_news_search_market, s4_eu, s5_people_jobs  # noqa: E402,F401
from run import trim  # noqa: E402

REPO = HERE.parents[1]                        # Modules/DataAPIs -> repository root
SNAPSHOT_DB = REPO / "DB" / "startupgo.db"     # tracked in git; changed only by `refresh.py snapshot`
RUNTIME_DIR = REPO / "DB" / "runtime"          # untracked: live DB, generated configs, search index, reports
SRC = {s.name: s for s in common.REGISTRY}


def db_path() -> Path:
    """The DB every script writes to: $STARTUPGO_DB, else the runtime copy (read at call time, so tests can override it)."""
    return Path(os.environ.get("STARTUPGO_DB") or RUNTIME_DIR / "startupgo.db")


def snapshot_path() -> Path:
    return Path(os.environ.get("STARTUPGO_SNAPSHOT_DB") or SNAPSHOT_DB)


def ensure_db(path: Path) -> bool:
    """Create ``path`` if missing: a consistent copy of the snapshot, else empty (caller seeds it). True if seeding is needed."""
    if path.exists():
        return False
    path.parent.mkdir(parents=True, exist_ok=True)
    snap = snapshot_path()
    if snap.exists() and snap.resolve() != path.resolve():
        src, dst = sqlite3.connect(f"file:{snap}?mode=ro", uri=True), sqlite3.connect(path)
        with dst:
            src.backup(dst)  # page-level copy, safe even if the snapshot is open elsewhere
        src.close()
        dst.close()
        return False
    return True


# ---------------------------------------------------------------------------
# DB setup
# ---------------------------------------------------------------------------
def open_db(path: Path | None = None) -> sqlite3.Connection:
    path = path or db_path()
    fresh = ensure_db(path)
    conn = sqlite3.connect(path, timeout=30)  # the backend may hold the DB briefly while a refresh writes
    if path.resolve() != snapshot_path().resolve():
        conn.execute("PRAGMA journal_mode=WAL")  # readers (backend) are not blocked by a long refresh
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA foreign_keys = ON")
    migrate(conn)
    conn.executescript((REPO / "DB" / "schema.sql").read_text())
    if fresh:
        conn.executescript((REPO / "DB" / "seed.sql").read_text())
    for s in common.REGISTRY:
        conn.execute("""INSERT INTO data_sources (name, section, access, endpoint, use, notes, last_status)
                        VALUES (?,?,?,?,?,?, 'not-run')
                        ON CONFLICT(name) DO UPDATE SET section=excluded.section, access=excluded.access,
                          endpoint=excluded.endpoint, use=excluded.use, notes=excluded.notes""",
                     (s.name, s.section, s.access, s.endpoint, s.use, s.notes))
    # Last results of `run.py` (sample runs) seed the status column
    summary = HERE / "data" / "_summary.json"
    if summary.exists():
        for name, v in json.loads(summary.read_text()).items():
            conn.execute("UPDATE data_sources SET last_status=?, last_info=? WHERE name=? AND last_status='not-run'",
                         (v["status"], v["info"][:300], name))
    conn.commit()
    return conn


def migrate(conn: sqlite3.Connection) -> None:
    """Bring an existing DB up to schema.sql before it is re-applied (CREATE IF NOT EXISTS cannot alter tables)."""
    tables = {r[0] for r in conn.execute("SELECT name FROM sqlite_master WHERE type='table'")}
    if "people" in tables:
        cols = {r[1] for r in conn.execute("PRAGMA table_info(people)")}
        for col in ("pdl_id", "education"):
            if col not in cols:
                conn.execute(f"ALTER TABLE people ADD COLUMN {col} TEXT")
    if "startup_parameter_status" in tables:
        sql = conn.execute("SELECT sql FROM sqlite_master WHERE name='startup_parameter_status'").fetchone()[0]
        if "not-applicable" not in sql:  # derived table (rebuilt by build_gaps): safe to drop and recreate
            conn.execute("DROP VIEW IF EXISTS startup_gaps")
            conn.execute("DROP TABLE startup_parameter_status")
    conn.commit()


def now() -> str:
    return datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M:%S")


# Personal data never written to raw_fetches (PDL person records carry contact details we do not need)
REDACT_KEYS = {"emails", "personal_emails", "work_email", "recommended_personal_email", "mobile_phone", "phone_numbers", "phones",
               "sex", "gender", "birth_year", "birth_date", "street_addresses", "location_street_address", "location_postal_code",
               "linkedin_url", "linkedin_username", "linkedin_id", "facebook_url", "facebook_username", "facebook_id",
               "twitter_url", "twitter_username", "github_url", "github_username", "profiles", "possible_emails", "possible_phones"}


def redact(o):
    if isinstance(o, dict):
        return {k: redact(v) for k, v in o.items() if k not in REDACT_KEYS}
    if isinstance(o, list):
        return [redact(x) for x in o]
    return o


def fetch(conn, source: str, startup_id: int | None = None, **params):
    """Call a registered scraper, log it in raw_fetches, return (data, fetch_id); data is None on failure."""
    s = SRC[source]
    try:
        data = s.fn(**params)
        status, err = "ok", None
    except common.Skipped as e:
        data, status, err = None, "skipped", str(e)
    except Exception as e:  # noqa: BLE001
        data, status, err = None, "error", str(e)[:500]
    stored = redact(data) if source == "pdl_person_search" else data
    payload = json.dumps(trim(stored), ensure_ascii=False, default=str) if data is not None else None
    cur = conn.execute("INSERT INTO raw_fetches (source_name, startup_id, params, status, error, size_bytes, payload) VALUES (?,?,?,?,?,?,?)",
                       (source, startup_id, json.dumps(params, ensure_ascii=False, default=str), status, err,
                        len(json.dumps(data, default=str)) if data is not None else None, payload))
    conn.execute("UPDATE data_sources SET last_status=?, last_info=?, last_run_at=? WHERE name=?",
                 (status, (err or "ok")[:300], now(), source))
    if s.slow:
        time.sleep(1)
    return data, cur.lastrowid


def signal(conn, sid, source, typ, title, url=None, observed_on=None, value=None, unit=None, details=None, conf="low", fetch_id=None):
    conn.execute("""INSERT OR IGNORE INTO startup_signals
                    (startup_id, source_name, signal_type, title, url, observed_on, value, unit, details, match_confidence, fetch_id)
                    VALUES (?,?,?,?,?,?,?,?,?,?,?)""",
                 (sid, source, typ, clean(title)[:500], url, observed_on, value, unit,
                  json.dumps(details, ensure_ascii=False, default=str) if details else None, conf, fetch_id))


def ext_id(conn, sid, typ, value, source, url=None, details=None, conf="medium", fetch_id=None):
    conn.execute("""INSERT OR REPLACE INTO startup_external_ids
                    (startup_id, id_type, external_id, source_name, url, details, match_confidence, fetch_id) VALUES (?,?,?,?,?,?,?,?)""",
                 (sid, typ, str(value), source, url, json.dumps(details, ensure_ascii=False, default=str) if details else None, conf, fetch_id))


def suggest(conn, st, field, value, source, evidence, conf, fetch_id):
    if value in (None, ""):
        return
    cur = st[field]
    if cur is not None and str(cur) == str(value):
        return
    conn.execute("""INSERT OR IGNORE INTO field_suggestions
                    (startup_id, field, value, current_value, source_name, evidence, match_confidence, fetch_id) VALUES (?,?,?,?,?,?,?,?)""",
                 (st["id"], field, str(value), None if cur is None else str(cur), source, evidence, conf, fetch_id))


def clean(s) -> str:
    return re.sub(r"<[^>]+>", "", str(s or "")).replace("&hellip;", "…").strip()


def norm(s) -> str:
    return re.sub(r"[^a-z0-9]", "", str(s or "").lower())


def domain(url) -> str | None:
    return urlparse(url).netloc.removeprefix("www.") if url else None


# ---------------------------------------------------------------------------
# Per-startup pulls
# ---------------------------------------------------------------------------
def ingest_startup(conn, st, yc_all, use_gdelt=False, paid=True):
    """All per-startup pulls. paid=False skips calls that spend credits (SerpApi, People Data Labs)."""
    sid, name, n = st["id"], st["name"], norm(st["name"])
    dom = domain(st["website"])

    # Registry: GLEIF (legal entity, jurisdiction, registration date, status)
    d, f = fetch(conn, "gleif_lei", sid, **{"filter[fulltext]": name, "page[size]": 10})
    for rec in (d or {}).get("data", []):
        a = rec["attributes"]
        legal = a["entity"]["legalName"]["name"]
        ent, reg = a["entity"], a["registration"]
        hq = (ent.get("headquartersAddress") or {}).get("country")
        if not norm(legal).startswith(n) or (ISO2.get(st["country"]) and hq != ISO2[st["country"]]):
            continue  # same name in another country is a different company
        det = {"legal_name": legal, "jurisdiction": ent.get("jurisdiction"), "status": ent.get("status"),
               "legal_form": (ent.get("legalForm") or {}).get("id"), "hq_city": (ent.get("headquartersAddress") or {}).get("city"),
               "hq_country": (ent.get("headquartersAddress") or {}).get("country"),
               "registered_on": (ent.get("creationDate") or reg.get("initialRegistrationDate") or "")[:10]}
        ext_id(conn, sid, "lei", a["lei"], "gleif_lei", f"https://search.gleif.org/#/record/{a['lei']}", det, "medium", f)
        signal(conn, sid, "gleif_lei", "registry", f"LEI record: {legal}", f"https://search.gleif.org/#/record/{a['lei']}",
               det["registered_on"] or None, details=det, conf="medium", fetch_id=f)
        if ent.get("creationDate"):
            suggest(conn, st, "founded_year", ent["creationDate"][:4], "gleif_lei", f"entity creationDate of {legal}", "medium", f)

    # Wikidata: exact English label match
    q = f"""SELECT ?item ?itemDescription ?inception ?website ?countryLabel ?hqLabel WHERE {{
      ?item rdfs:label "{name}"@en .
      OPTIONAL {{ ?item wdt:P571 ?inception }} OPTIONAL {{ ?item wdt:P856 ?website }}
      OPTIONAL {{ ?item wdt:P17 ?country }} OPTIONAL {{ ?item wdt:P159 ?hq }}
      SERVICE wikibase:label {{ bd:serviceParam wikibase:language "en". }} }} LIMIT 10"""
    d, f = fetch(conn, "wikidata_sparql", sid, query=q)
    for b in ((d or {}).get("results") or {}).get("bindings", []):
        g = {k: v["value"] for k, v in b.items()}
        desc = g.get("itemDescription", "")
        web_match = dom and dom in g.get("website", "")
        if not (web_match or re.search(r"compan|startup|business|enterprise|manufactur", desc, re.I)):
            continue
        conf = "high" if web_match else "medium"
        qid = g["item"].rsplit("/", 1)[-1]
        ext_id(conn, sid, "wikidata_qid", qid, "wikidata_sparql", g["item"], g, conf, f)
        if g.get("inception"):
            suggest(conn, st, "founded_year", g["inception"][:4], "wikidata_sparql", f"{qid} P571 inception", conf, f)
        if g.get("website"):
            suggest(conn, st, "website", g["website"], "wikidata_sparql", f"{qid} P856", conf, f)
        if g.get("hqLabel"):
            suggest(conn, st, "city", g["hqLabel"], "wikidata_sparql", f"{qid} P159 HQ", conf, f)

    # YC OSS: exact name or same domain
    for c in yc_all or []:
        if norm(c.get("name")) == n or (dom and dom == domain(c.get("website"))):
            det = {k: c.get(k) for k in ("batch", "team_size", "status", "isHiring", "industry", "subindustry", "tags", "regions", "stage", "launched_at", "one_liner")}
            ext_id(conn, sid, "yc_slug", c["slug"], "yc_oss_companies", c.get("url"), det, "high")
            signal(conn, sid, "yc_oss_companies", "profile", f"YC {c.get('batch')}: {c.get('one_liner')}", c.get("url"),
                   value=c.get("team_size"), unit="employees", details=det, conf="high")
            if c.get("launched_at"):
                suggest(conn, st, "founded_year", datetime.fromtimestamp(c["launched_at"], timezone.utc).year, "yc_oss_companies", "YC launched_at", "medium", None)

    # Patents: Google Patents filtered by assignee; SerpApi when the free endpoint is blocked (it 503s under load)
    d, f = fetch(conn, "google_patents_xhr", sid, q="", num=25, assignee=name)
    src, pats = "google_patents_xhr", (d or {}).get("patents", [])
    if d is None and paid and os.environ.get("SERPAPI_KEY"):
        d, f = fetch(conn, "serpapi_google_patents", sid, assignee=name, num=50)
        src, pats = "serpapi_google_patents", (d or {}).get("organic_results", [])
    for p in pats:
        if n not in norm(p.get("assignee")):
            continue
        signal(conn, sid, src, "patent", f"{p['publication_number']}: {clean(p['title'])}",
               f"https://patents.google.com/patent/{p['publication_number']}", p.get("priority_date"),
               details={k: p.get(k) for k in ("assignee", "inventor", "filing_date", "publication_date", "grant_date", "pdf")}, conf="high", fetch_id=f)

    # Papers: OpenAlex full-text phrase search (mentions, not authorship => low)
    d, f = fetch(conn, "openalex", sid, search=f'"{name}"', **{"per-page": 10, "select": "id,doi,title,publication_year,cited_by_count"})
    for w in (d or {}).get("results", []):
        if w.get("title"):
            signal(conn, sid, "openalex", "paper", w["title"], w.get("doi") or w["id"], str(w.get("publication_year") or ""),
                   w.get("cited_by_count"), "citations", conf="low", fetch_id=f)

    # News: Google News RSS, keep items whose title names the company
    d, f = fetch(conn, "google_news_rss", sid, q=f'"{name}"', limit=25)
    for it in d or []:
        if n in norm(it.get("title")):
            pub = it.get("pubDate")
            try:
                pub = datetime.strptime(pub, "%a, %d %b %Y %H:%M:%S %Z").strftime("%Y-%m-%d")
            except (TypeError, ValueError):
                pass
            signal(conn, sid, "google_news_rss", "news", it["title"], it.get("link"), pub,
                   details={"source": it.get("source")}, conf="medium", fetch_id=f)

    # Launches: Hacker News stories naming the company
    d, f = fetch(conn, "hn_algolia", sid, query=name, tags="story", hitsPerPage=20)
    for h in (d or {}).get("hits", []):
        if n in norm(h.get("title")):
            signal(conn, sid, "hn_algolia", "launch", h["title"], f"https://news.ycombinator.com/item?id={h['objectID']}",
                   (h.get("created_at") or "")[:10], h.get("points"), "points", {"comments": h.get("num_comments"), "url": h.get("url")}, "medium", f)

    # Open source: GitHub repos whose owner or name matches
    d, f = fetch(conn, "github_search_repos", sid, q=f"{name} in:name,description", sort="stars", per_page=10)
    for r in (d or {}).get("items", []):
        home = bool(dom and dom in (r.get("homepage") or ""))
        owner = norm(r["owner"]["login"])
        if home or (owner.startswith(n) and len(owner) - len(n) <= 3):  # e.g. clearbothk; not NotPlaza
            signal(conn, sid, "github_search_repos", "repo", r["full_name"], r["html_url"], (r.get("pushed_at") or "")[:10],
                   r.get("stargazers_count"), "stars", {"forks": r.get("forks_count"), "language": r.get("language"), "description": r.get("description")},
                   "high" if home else "low", f)  # owner-name match alone is often an unrelated user

    # US fundraises: SEC Form D full-text (US startups only)
    if st["country"] == "United States":
        d, f = fetch(conn, "sec_edgar_fulltext_formD", sid, q=f'"{name}"', forms="D,D/A")
        for h in ((d or {}).get("hits") or {}).get("hits", [])[:20]:
            src = h["_source"]
            disp = " / ".join(src.get("display_names", []))
            if n in norm(disp):
                acc = h["_id"].split(":")[0]
                cik = (src.get("ciks") or [""])[0].lstrip("0")
                signal(conn, sid, "sec_edgar_fulltext_formD", "filing", f"Form {src.get('root_forms', ['D'])[0]}: {disp}",
                       f"https://www.sec.gov/Archives/edgar/data/{cik}/{acc.replace('-', '')}/", src.get("file_date"),
                       details={"accession": acc, "ciks": src.get("ciks")}, conf="high", fetch_id=f)
                ext_id(conn, sid, "sec_cik", cik, "sec_edgar_fulltext_formD", f"https://www.sec.gov/cgi-bin/browse-edgar?action=getcompany&CIK={cik}", None, "high", f)

    if dom:
        # Web history: first capture + captures per year
        d, f = fetch(conn, "wayback_cdx", sid, url=dom, output="json", collapse="timestamp:4", filter="statuscode:200", fl="timestamp,original")
        rows = (d or [])[1:] if isinstance(d, list) else []
        if rows:
            years = sorted({r[0][:4] for r in rows})
            signal(conn, sid, "wayback_cdx", "web_history", f"{dom}: archived since {years[0]}",
                   f"https://web.archive.org/web/*/{dom}", f"{rows[0][0][:4]}-{rows[0][0][4:6]}-{rows[0][0][6:8]}", len(years), "years captured",
                   {"years": years}, "high", f)
            if st["founded_year"] is None:  # first capture is only an upper bound, so it can't contradict a known year
                suggest(conn, st, "founded_year", years[0], "wayback_cdx",
                        f"first archived capture of {dom} (upper bound on founding)", "low", f)
        # Website content (markdown) for later LLM extraction
        d, f = fetch(conn, "jina_reader", sid, url=st["website"])
        if d and d.get("markdown"):
            md = d["markdown"]
            title = re.search(r"^Title: (.+)$", md, re.M)
            signal(conn, sid, "jina_reader", "website", title.group(1) if title else dom, st["website"], now()[:10], len(md), "chars",
                   {"excerpt": md[:1500]}, "high", f)

    if use_gdelt:
        d, f = fetch(conn, "gdelt_doc", sid, query=f'"{name}"', mode="artlist", format="json", maxrecords=25, timespan="12months")
        for a in (d or {}).get("articles", []) if isinstance(d, dict) else []:
            signal(conn, sid, "gdelt_doc", "news", a["title"], a["url"], a.get("seendate", "")[:8], details={"domain": a.get("domain")}, conf="low", fetch_id=f)

    if st["country"] == "United Kingdom":
        ingest_companies_house(conn, st)
    # Key-based sources: attempted so the gap report records why they are empty
    if paid:
        ingest_pdl(conn, st)
    fetch(conn, "opencorporates", sid, q=name)
    fetch(conn, "product_hunt", sid)
    conn.commit()


def ingest_companies_house(conn, st):
    """UK register: pick the matching company, then profile, officers, PSC, capital filings, insolvency."""
    sid, name, n = st["id"], st["name"], norm(st["name"])
    d, f = fetch(conn, "uk_companies_house", sid, q=name, items_per_page=20)
    assignees = {norm(r[0]) for r in conn.execute(
        "SELECT json_extract(details,'$.assignee') FROM startup_signals WHERE startup_id=? AND signal_type='patent'", (sid,)) if r[0]}
    best, best_score = None, 0
    for c in (d or {}).get("items", []):
        t = norm(c["title"])
        if not t.startswith(n):
            continue
        base = lambda x: re.sub(r"(limited|ltd)$", "", x)  # noqa: E731
        score = (3 if base(t) == n else 0) \
            + (4 if any(base(t) == base(a) for a in assignees) else 0) \
            + (-5 if c.get("company_status") == "dissolved" else 2) \
            + (1 if st["city"] and st["city"].lower() in (c.get("address_snippet") or "").lower() else 0)
        # patent assignee name beats a bare name match; a dissolved company is almost never the live startup
        if score > best_score:
            best, best_score = c, score
    if not best:
        return
    num, conf = best["company_number"], "high" if best_score >= 6 else "medium"
    ch_url = f"https://find-and-update.company-information.service.gov.uk/company/{num}"

    prof, f = fetch(conn, "uk_companies_house_company", sid, number=num)
    prof = prof or {}
    addr = prof.get("registered_office_address") or {}
    det = {"company_name": prof.get("company_name"), "status": prof.get("company_status"), "status_detail": prof.get("company_status_detail"),
           "type": prof.get("type"), "jurisdiction": prof.get("jurisdiction"), "date_of_creation": prof.get("date_of_creation"),
           "sic_codes": prof.get("sic_codes"), "registered_office": ", ".join(v for k, v in addr.items() if isinstance(v, str)),
           "accounts_last_made_up_to": (prof.get("accounts") or {}).get("last_accounts", {}).get("made_up_to"),
           "accounts_type": (prof.get("accounts") or {}).get("last_accounts", {}).get("type"),
           "has_charges": prof.get("has_charges"), "has_insolvency_history": prof.get("has_insolvency_history")}
    ext_id(conn, sid, "company_number", num, "uk_companies_house_company", ch_url, det, conf, f)
    signal(conn, sid, "uk_companies_house_company", "registry", f"Companies House: {det['company_name']} ({det['status']})", ch_url,
           det["date_of_creation"], details=det, conf=conf, fetch_id=f)
    if det["date_of_creation"]:
        suggest(conn, st, "founded_year", det["date_of_creation"][:4], "uk_companies_house_company", f"{num} date_of_creation {det['date_of_creation']}", conf, f)
    if addr.get("locality"):
        suggest(conn, st, "city", addr["locality"], "uk_companies_house_company", f"{num} registered office", "low", f)

    d, f = fetch(conn, "uk_companies_house_company", sid, number=num, path="officers", items_per_page=100)
    officers = (d or {}).get("items", [])
    active = [o for o in officers if not o.get("resigned_on")]
    if officers:
        people = [{k: o.get(k) for k in ("name", "officer_role", "appointed_on", "resigned_on", "occupation", "nationality", "country_of_residence")} for o in officers]
        signal(conn, sid, "uk_companies_house_company", "profile", f"Officers: {len(active)} active, {len(officers) - len(active)} resigned",
               f"{ch_url}/officers", now()[:10], len(active), "officers", {"officers": people}, conf, f)
        founding = [o["name"] for o in officers if o.get("officer_role") == "director" and o.get("appointed_on") == det["date_of_creation"]]
        if founding:
            signal(conn, sid, "uk_companies_house_company", "profile", f"Founding directors: {'; '.join(founding)}", f"{ch_url}/officers",
                   det["date_of_creation"], len(founding), "founders", {"basis": "directors appointed on the incorporation date"}, "medium", f)

    d, f = fetch(conn, "uk_companies_house_company", sid, number=num, path="persons-with-significant-control", items_per_page=100)
    for p in (d or {}).get("items", []):
        signal(conn, sid, "uk_companies_house_company", "registry", f"PSC: {p.get('name')}", f"{ch_url}/persons-with-significant-control",
               p.get("notified_on"), None, "psc", {"kind": p.get("kind"), "natures_of_control": p.get("natures_of_control"), "ceased_on": p.get("ceased_on")}, conf, f)

    d, f = fetch(conn, "uk_companies_house_company", sid, number=num, path="filing-history", category="capital", items_per_page=100)
    for it in (d or {}).get("items", []):
        dv = it.get("description_values") or {}
        caps = dv.get("capital") or []
        cap_txt = "; ".join(f"{c.get('currency')} {c.get('figure')}" for c in caps)
        signal(conn, sid, "uk_companies_house_company", "filing", f"{it.get('type')}: {it.get('description', '').replace('-', ' ')}" + (f" ({cap_txt})" if cap_txt else ""),
               f"https://find-and-update.company-information.service.gov.uk{(it.get('links') or {}).get('self', '')}", dv.get("date") or it.get("date"),
               details={"type": it.get("type"), "capital": caps, "filed_on": it.get("date")}, conf=conf, fetch_id=f)

    if det["has_insolvency_history"]:
        d, f = fetch(conn, "uk_companies_house_company", sid, number=num, path="insolvency")
        for case in (d or {}).get("cases", []):
            dates = {x.get("type"): x.get("date") for x in case.get("dates", [])}
            pract = [p.get("name") for p in case.get("practitioners", [])]
            signal(conn, sid, "uk_companies_house_company", "registry", f"Insolvency case {case.get('number')}: {case.get('type')}", f"{ch_url}/insolvency",
                   next(iter(dates.values()), None), None, "insolvency", {"dates": dates, "practitioners": pract}, "high", f)
    conn.commit()


def ingest_pdl(conn, st):
    """People Data Labs company enrichment (1 credit per match): headcount, founded, funding totals, profiles."""
    if not os.environ.get("PDL_API_KEY"):
        fetch(conn, "people_data_labs", st["id"], name=st["name"])  # records the skip
        return
    sid, n = st["id"], norm(st["name"])
    site = st["website"] or (conn.execute("SELECT value FROM field_suggestions WHERE startup_id=? AND field='website' AND status!='rejected' "
                                          "ORDER BY match_confidence='high' DESC LIMIT 1", (sid,)).fetchone() or [None])[0]
    q = {"website": domain(site)} if site else {"name": st["name"], "country": st["country"]}
    d, f = fetch(conn, "people_data_labs", sid, **q, min_likelihood=4)
    same_site = bool(site and d and d.get("website") == domain(site))  # e.g. clearbot.org is listed as "Clear Robotics"
    if not d or d.get("status") != 200 or not (same_site or n in norm(d.get("display_name") or d.get("name"))):
        return
    conf = "high" if st["website"] and domain(st["website"]) == d.get("website") else "medium"
    url = f"https://{d['linkedin_url']}" if d.get("linkedin_url") else None
    loc = d.get("location") or {}
    det = {k: d.get(k) for k in ("display_name", "size", "employee_count", "founded", "industry", "industry_v2", "type", "headline", "summary",
                                 "linkedin_url", "profiles", "employee_count_by_country", "likelihood", "dataset_version")}
    det["location"] = loc.get("name")
    ext_id(conn, sid, "pdl_id", d["id"], "people_data_labs", url, det, conf, f)
    if d.get("linkedin_url"):
        ext_id(conn, sid, "linkedin_company", d["linkedin_url"], "people_data_labs", url, None, conf, f)
    if d.get("employee_count") is not None:
        signal(conn, sid, "people_data_labs", "profile", f"Employees: {d['employee_count']} ({d.get('size')})", url, now()[:10],
               d["employee_count"], "employees", {"by_country": d.get("employee_count_by_country")}, conf, f)
    if d.get("total_funding_raised"):
        signal(conn, sid, "people_data_labs", "profile",
               f"Funding: ${d['total_funding_raised']:,.0f} raised in {d.get('number_funding_rounds')} rounds; latest {d.get('latest_funding_stage')} on {d.get('last_funding_date')}",
               url, d.get("last_funding_date"), d["total_funding_raised"], "usd_raised",
               {"rounds": d.get("number_funding_rounds"), "stages": d.get("funding_stages"), "latest_stage": d.get("latest_funding_stage")}, conf, f)
    if d.get("founded"):
        suggest(conn, st, "founded_year", d["founded"], "people_data_labs", f"PDL founded (likelihood {d.get('likelihood')})", conf, f)
    if loc.get("locality"):
        suggest(conn, st, "city", loc["locality"].title(), "people_data_labs", f"PDL HQ: {loc.get('name')}", "low", f)
    if not st["website"] and d.get("website"):
        suggest(conn, st, "website", f"https://{d['website']}", "people_data_labs", "PDL website", conf, f)
    conn.commit()


def ingest_serpapi(conn, st):
    """Paid-quota enrichment (2 SerpApi searches per startup): website, knowledge panel facts, job postings."""
    if not os.environ.get("SERPAPI_KEY"):
        return
    sid, name, n = st["id"], st["name"], norm(st["name"])

    d, f = fetch(conn, "serpapi_google", sid, q=f'"{name}" {st["sector"]} company', num=10)
    d = d or {}
    for r in d.get("organic_results", []):
        stem = norm((domain(r.get("link")) or "").split(".")[0])
        if stem.startswith(n) or (len(stem) >= 5 and n.startswith(stem)):  # domain stem must look like the company name
            root = f"https://{urlparse(r['link']).netloc}"
            if st["website"] is None:
                suggest(conn, st, "website", root, "serpapi_google", f"organic #{r.get('position')}: {r.get('title')}", "medium", f)
            break
    kg = d.get("knowledge_graph") or {}
    kg_dom = domain(kg.get("website"))
    own_site = bool(kg_dom and (domain(st["website"]) == kg_dom or norm(kg_dom.split(".")[0]).startswith(n)))
    is_company = kg.get("entity_type") != "local_nav" and re.search(r"compan|startup|business|manufactur", str(kg.get("type", "")), re.I)
    if kg and n in norm(kg.get("title")) and (own_site or is_company):  # e.g. "Oceanium" also matches a Rotterdam aquarium
        kg_url = kg.get("website") or kg.get("source", {}).get("link")
        if kg.get("website") and st["website"] is None:
            suggest(conn, st, "website", kg["website"], "serpapi_google", "Google knowledge panel", "high", f)
        if kg.get("founded"):
            y = re.search(r"(19|20)\d{2}", str(kg["founded"]))
            if y:
                suggest(conn, st, "founded_year", y.group(0), "serpapi_google", f"knowledge panel founded: {kg['founded']}", "medium", f)
        if kg.get("headquarters"):
            suggest(conn, st, "city", kg["headquarters"].split(",")[0].strip(), "serpapi_google", f"knowledge panel HQ: {kg['headquarters']}", "medium", f)
        emp = kg.get("number_of_employees") or kg.get("employees")
        if emp:
            m = re.search(r"[\d,]+", str(emp))
            signal(conn, sid, "serpapi_google", "profile", f"Employees: {emp}", kg_url, now()[:10],
                   float(m.group(0).replace(",", "")) if m else None, "employees", {"raw": emp}, "medium", f)
        founders = kg.get("founders") or kg.get("founder")
        if founders:
            names = [x.get("name", x) if isinstance(x, dict) else x for x in (founders if isinstance(founders, list) else [founders])]
            signal(conn, sid, "serpapi_google", "profile", f"Founders: {', '.join(map(str, names))}", kg_url, now()[:10],
                   len(names), "founders", {"founders": names}, "medium", f)
        facts = {k: v for k, v in kg.items() if isinstance(v, (str, int, float)) and k not in ("kgmid", "knowledge_graph_search_link", "serpapi_knowledge_graph_search_link")}
        signal(conn, sid, "serpapi_google", "profile", f"Knowledge panel: {kg.get('title')}", kg_url, now()[:10], details=facts, conf="medium", fetch_id=f)

    d, f = fetch(conn, "serpapi_google_jobs", sid, q=name)
    for j in (d or {}).get("jobs_results", []):
        if norm(j.get("company_name")) != n and not norm(j.get("company_name")).startswith(n):
            continue
        ext = j.get("detected_extensions") or {}
        link = (j.get("apply_options") or [{}])[0].get("link") or j.get("share_link")
        signal(conn, sid, "serpapi_google_jobs", "job", f"{j.get('title')} ({j.get('location')})", link, now()[:10],
               details={"company": j.get("company_name"), "via": j.get("via"), "posted": ext.get("posted_at"),
                        "schedule": ext.get("schedule_type"), "remote": ext.get("work_from_home")}, conf="high", fetch_id=f)
    conn.commit()


# ---------------------------------------------------------------------------
# Funding opportunities and market indicators
# ---------------------------------------------------------------------------
def ingest_funding(conn):
    d, f = fetch(conn, "eu_sedia_calls", None, text="ocean", pageSize=50)
    for r in (d or {}).get("results", []):
        m = r.get("metadata", {})
        first = lambda k: (m.get(k) or [None])[0]  # noqa: E731
        ident = first("identifier") or r.get("reference")
        conn.execute("""INSERT OR REPLACE INTO funding_opportunities
                        (source_name, external_ref, kind, title, status, opens_on, deadline, organisation, url, fetch_id) VALUES (?,?,?,?,?,?,?,?,?,?)""",
                     ("eu_sedia_calls", ident, "grant_call", first("title") or r.get("summary") or ident,
                      {"31094501": "forthcoming", "31094502": "open", "31094503": "closed"}.get(first("status"), first("status")),
                      (first("startDate") or "")[:10] or None, (first("deadlineDate") or "")[:10] or None, first("frameworkProgramme"),
                      f"https://ec.europa.eu/info/funding-tenders/opportunities/portal/screen/opportunities/topic-details/{ident}", f))

    d, f = fetch(conn, "grants_gov", None, keyword="ocean", rows=50, oppStatuses="forecasted|posted")
    for o in ((d or {}).get("data") or {}).get("oppHits", []):
        conn.execute("""INSERT OR REPLACE INTO funding_opportunities
                        (source_name, external_ref, kind, title, status, opens_on, deadline, organisation, url, fetch_id) VALUES (?,?,?,?,?,?,?,?,?,?)""",
                     ("grants_gov", o["number"], "grant_call", o["title"], o.get("oppStatus"), o.get("openDate"), o.get("closeDate") or None,
                      o.get("agency"), f"https://www.grants.gov/search-results-detail/{o['id']}", f))

    d, f = fetch(conn, "ukri_gateway_to_research", None, q="ocean", s=50)
    for p in (d or {}).get("project", []):
        conn.execute("""INSERT OR REPLACE INTO funding_opportunities
                        (source_name, external_ref, kind, title, status, organisation, url, fetch_id) VALUES (?,?,?,?,?,?,?,?)""",
                     ("ukri_gateway_to_research", p["id"], "project", p["title"], p.get("status"), p.get("leadFunder"),
                      f"https://gtr.ukri.org/projects?ref={p.get('grantReference', p['id'])}", f))

    d, f = fetch(conn, "ted_eu_tenders", None, query="FT~ocean AND publication-date>=20250101", limit=50)
    for t in (d or {}).get("notices", []):
        buyer = t.get("buyer-name") or {}
        buyer = (buyer.get("eng") or next(iter(buyer.values()), [None]))[0] if isinstance(buyer, dict) else buyer
        title = t.get("notice-title") or {}
        title = title.get("eng") or next(iter(title.values()), "") if isinstance(title, dict) else title
        conn.execute("""INSERT OR REPLACE INTO funding_opportunities
                        (source_name, external_ref, kind, title, status, opens_on, organisation, url, fetch_id) VALUES (?,?,?,?,?,?,?,?,?)""",
                     ("ted_eu_tenders", t["publication-number"], "tender", title or t["publication-number"], t.get("notice-type"),
                      (t.get("publication-date") or "")[:10], buyer, f"https://ted.europa.eu/en/notice/-/detail/{t['publication-number']}", f))
    conn.commit()


WB_COUNTRIES = {"United Kingdom": "GBR", "United States": "USA", "Faroe Islands": "FRO", "Portugal": "PRT",
                "Namibia": "NAM", "Hong Kong": "HKG", "Finland": "FIN"}
ISO2 = {"United Kingdom": "GB", "United States": "US", "Faroe Islands": "FO", "Portugal": "PT", "Namibia": "NA",
        "Hong Kong": "HK", "Finland": "FI", "Netherlands": "NL"}
WB_INDICATORS = {"NY.GDP.MKTP.CD": ("GDP (current US$)", "USD"),
                 "ER.FSH.AQUA.MT": ("Aquaculture production", "metric tons"),
                 "ER.FSH.CAPT.MT": ("Capture fisheries production", "metric tons")}


def ingest_market(conn):
    countries = {r["country"] for r in conn.execute("SELECT DISTINCT country FROM startups")} | {"Finland"}
    isos = ";".join(WB_COUNTRIES[c] for c in countries if c in WB_COUNTRIES)
    for code, (label, unit) in WB_INDICATORS.items():
        d, f = fetch(conn, "world_bank", None, iso=isos, code=code, mrv=10, per_page=500)
        for r in (d[1] if isinstance(d, list) and len(d) > 1 and d[1] else []):
            if r.get("value") is not None:
                conn.execute("INSERT OR REPLACE INTO market_indicators (source_name, indicator_code, indicator_name, geo, period, value, unit, fetch_id) VALUES (?,?,?,?,?,?,?,?)",
                             ("world_bank", code, label, r["countryiso3code"], r["date"], r["value"], unit, f))

    # Eurostat aquaculture production, total of all species, tonnes live weight, for EU countries of interest
    for geo in ("FI", "PT", "NO", "EU27_2020"):
        d, f = fetch(conn, "eurostat", None, code="fish_aq2a", geo=geo, species="F00", unit="TLW", aquaenv="TOTAL", aquameth="TOTAL", fishreg="0", sinceTimePeriod="2015")
        if not isinstance(d, dict) or "dimension" not in d:
            continue
        times = d["dimension"]["time"]["category"]["index"]
        for period, idx in times.items():
            v = d["value"].get(str(idx))
            if v is not None:
                conn.execute("INSERT OR REPLACE INTO market_indicators (source_name, indicator_code, indicator_name, geo, period, value, unit, fetch_id) VALUES (?,?,?,?,?,?,?,?)",
                             ("eurostat", "fish_aq2a", "Aquaculture production, all species", geo, period, v, "tonnes live weight", f))
    conn.commit()


# ---------------------------------------------------------------------------
# Parameter catalogue + gaps
# ---------------------------------------------------------------------------
SECTION_PRIORITY = {"A": "P0", "B": "P0", "C": "P0", "D": "P0", "F": "P0", "G": "P0", "K": "P0",
                    "E": "P1", "H": "P1", "J": "P1", "N": "P1", "O": "P1",
                    "I": "P2", "L": "P2", "M": "P2", "P": "P2", "Q": "P2", "R": "P2", "S": "P2", "T": "P2", "U": "P2"}

# (section, item) -> (coverage, filled_by rule, sources). Anything not listed is 'missing'.
COVER = {
    ("A", 1): ("auto", "col:id", "internal"),
    ("A", 2): ("auto", "col:name", "seed; gleif_lei legal name"),
    ("A", 3): ("auto", "col:website|suggest:website", "seed; wikidata_sparql"),
    ("A", 4): ("auto", "ext:company_number|ext:lei", "uk_companies_house, gleif_lei; opencorporates*"),
    ("A", 5): ("auto", "col:city|suggest:city", "seed; gleif_lei HQ; wikidata_sparql"),
    ("A", 6): ("auto", "col:founded_year|suggest:founded_year", "seed; gleif_lei, wikidata_sparql, wayback_cdx, yc_oss"),
    ("A", 7): ("auto", "col:founded_year|suggest:founded_year", "derived from founding date"),
    ("A", 8): ("auto", "col:sector", "seed"),
    ("A", 9): ("partial", "ext:pdl_id|ext:yc_slug", "people_data_labs industry_v2, yc_oss tags"),
    ("A", 13): ("auto", "ext:company_number|ext:lei|ext:yc_slug", "uk_companies_house status, gleif_lei, yc_oss"),
    ("A", 14): ("auto", "unit:employees", "people_data_labs employee_count, yc_oss team_size"),
    ("A", 16): ("auto", "col:stage", "seed"),
    ("A", 17): ("auto", "ext:company_number|ext:lei", "uk_companies_house type, gleif_lei legal form"),
    ("A", 18): ("auto", "col:tagline", "seed"),
    ("A", 19): ("partial", "col:description|signal:website", "seed description; jina_reader website text"),
    ("A", 20): ("partial", "col:sector", "seed"),
    ("B", 1): ("auto", "founders|unit:founders", "uk_companies_house founding directors; pdl_person_search founder titles"),
    ("B", 2): ("partial", "founders|unit:officers", "uk_companies_house officer roles; pdl_person_search titles"),
    ("B", 5): ("partial", "ventures", "uk_companies_house_officer appointments; pdl_person_search venture-like roles (founder/owner/CEO/MD)"),
    ("B", 9): ("partial", "education", "pdl_person_search education (degree level only; school prestige deliberately not scored)"),
    ("B", 22): ("partial", "board|unit:officers", "uk_companies_house directors, sec_form_d_document directors, pdl_person_search board titles"),
    ("B", 19): ("partial", "feature:open_roles", "job_boards, serpapi_google_jobs open roles (0 = checked, none open)"),
    ("D", 4): ("partial", "market", "world_bank, eurostat, oecd_sdmx"),
    ("D", 8): ("partial", "market", "world_bank, eurostat"),
    ("D", 18): ("partial", "market", "world_bank, eurostat, oecd_sdmx"),
    ("E", 1): ("partial", "col:description|signal:website", "seed; jina_reader"),
    ("E", 11): ("partial", "na_unless_software|signal:repo", "github_search_repos (not meaningful for hardware/biotech)"),
    ("E", 17): ("auto", "signal:patent", "google_patents_xhr; serpapi_google_patents*, epo_ops*, patentsview*, lens_org*"),
    ("E", 18): ("partial", "signal:patent", "google_patents_xhr (grant status, family)"),
    ("E", 19): ("partial", "signal:paper", "openalex, crossref, semantic_scholar*"),
    ("E", 20): ("auto", "unit:trl|assess", "blueinvest_profile self-reported TRL; readiness_assessments.trl (seed estimate)"),
    ("F", 20): ("partial", "signal:news", "news mentions of pilots"),
    ("F", 23): ("partial", "signal:news", "news mentions of customers"),
    ("J", 1): ("partial", "xpeers|peers", "BlueInvest pipeline peer universe; similar startups in DB"),
    ("J", 3): ("partial", "peerfunding", "funding data of similar startups in DB"),
    ("J", 13): ("auto", "signal:patent", "google_patents_xhr"),
    ("K", 1): ("auto", "unit:usd_raised|rounds", "people_data_labs total raised; funding_rounds; sec_edgar Form D"),
    ("K", 2): ("auto", "unit:usd_raised|rounds", "people_data_labs round count; funding_rounds"),
    ("K", 3): ("auto", "unit:usd_raised|rounds", "people_data_labs last funding date; funding_rounds"),
    ("K", 4): ("auto", "unit:usd_raised|rounds", "people_data_labs latest stage; funding_rounds"),
    ("K", 5): ("auto", "rounds", "funding_rounds; sec_edgar Form D"),
    ("K", 9): ("auto", "rounds", "funding_rounds.lead_investors/notes"),
    ("K", 10): ("auto", "rounds", "funding_rounds.lead_investors"),
    ("L", 1): ("partial", "rounds", "investor names only; wikidata_sparql for profiles"),
    ("M", 1): ("partial", "col:founded_year|suggest:founded_year|signal:web_history", "founding date; wayback_cdx"),
    ("N", 1): ("auto", "ext:company_number|ext:lei", "uk_companies_house, gleif_lei"),
    ("N", 2): ("partial", "unit:psc|ext:lei", "uk_companies_house PSC register, gleif_lei parents"),
    ("N", 20): ("partial", "unit:insolvency|ext:company_number", "uk_companies_house insolvency + charges flags"),
    ("O", 3): ("partial", "feature:distress_flag|feature:no_round_24m|unit:insolvency", "distress flag, 730-day funding rule, insolvency cases"),
    ("Q", 4): ("auto", "na_unless_software|signal:repo", "github_search_repos (not meaningful for hardware/biotech)"),
    ("Q", 6): ("partial", "feature:technical_open_roles", "job_boards, serpapi_google_jobs (engineering / science / R&D roles)"),
    ("Q", 7): ("partial", "feature:commercial_open_roles", "job_boards, serpapi_google_jobs (sales / BD / marketing / customer roles)"),
    ("Q", 8): ("partial", "jobsnapshots", "job_boards / serpapi_google_jobs: needs postings from at least two dates"),
    ("Q", 9): ("partial", "na_unless_software|signal:launch", "hn_algolia; product_hunt* (not meaningful for hardware/biotech)"),
    ("Q", 10): ("partial", "signal:news", "google_news_rss, gdelt_doc"),
    ("Q", 11): ("partial", "signal:news", "google_news_rss, gdelt_doc"),
    ("Q", 12): ("auto", "signal:news", "google_news_rss, gdelt_doc; newsapi*"),
    ("Q", 14): ("auto", "signal:paper", "openalex, crossref"),
    ("Q", 15): ("auto", "signal:patent", "google_patents_xhr"),
    ("Q", 19): ("partial", "signal:web_history", "wayback_cdx, common_crawl_index"),
    ("Q", 20): ("auto", "rounds|signal:filing", "funding_rounds, sec_edgar Form D, uk_companies_house SH01 allotments"),
    ("K", 14): ("partial", "events:total_shares", "uk_sh01 statement of capital (total shares after each allotment)"),
    ("S", 3): ("partial", "kpi:D", "startup_ocean_kpis area D (climate)"),
    ("S", 4): ("partial", "kpi:E", "startup_ocean_kpis"),
    ("S", 5): ("partial", "kpi:B", "startup_ocean_kpis area B (pollution)"),
    ("S", 6): ("partial", "kpi:F", "startup_ocean_kpis area F (people)"),
    ("S", 7): ("partial", "kpi:F", "startup_ocean_kpis area F"),
    ("S", 9): ("partial", "kpi", "evidence_level 0-4 per KPI"),
    ("T", 1): ("missing", None, "needs revenue data"),
    ("T", 12): ("partial", "unit:employees", "headcount snapshots across runs"),
    ("T", 19): ("auto", "always", "computed from startup_parameter_status"),
    ("T", 20): ("auto", "always", "match_confidence / readiness confidence columns"),
    ("U", 1): ("auto", "always", "sources, *.source_url, raw_fetches"),
    ("U", 2): ("auto", "always", "raw_fetches.fetched_at"),
    ("U", 3): ("auto", "always", "startup_signals.observed_on"),
    ("U", 4): ("partial", "always", "match_confidence; field_suggestions.status"),
    ("U", 6): ("auto", "always", "match_confidence"),
    ("U", 7): ("auto", "always", "field_suggestions.current_value vs value"),
    ("U", 8): ("auto", "always", "NULL = unknown (never 0)"),
    ("U", 9): ("partial", "always", "data_sources.notes"),
    ("U", 12): ("auto", "always", "raw_fetches.source_name"),
    ("U", 14): ("partial", "always", "raw_fetches keeps every call"),
    ("U", 15): ("partial", "rounds", "funding_rounds.currency"),
}


def parse_parameters():
    text = (HERE / "parameters.txt").read_text()
    out, sec, name = [], None, None
    for line in text.splitlines():
        m = re.match(r"^([A-X])\. (.+)$", line.strip())
        if m:
            sec, name = m.group(1), m.group(2).title()
            continue
        m = re.match(r"^(\d+)\. (.+)$", line)
        if m and sec and sec <= "U":
            item, rest = int(m.group(1)), m.group(2).strip()
            nm, _, desc = rest.partition(" — ")
            out.append((sec, name, item, nm.strip(), desc.strip() or None))
    return out


def evaluate(conn, rule, st):
    """Return (status, evidence_count, detail) for one startup and one filled_by rule."""
    sid = st["id"]
    best = ("empty", 0, None)
    for part in rule.split("|"):
        kind, _, arg = part.partition(":")
        n = 0
        if kind == "always":
            return ("filled", 1, "system field")
        if kind == "na_unless_software":
            ind = " ".join(str(json.loads(r[0] or "{}").get("industry_v2") or "") for r in conn.execute(
                "SELECT details FROM startup_external_ids WHERE startup_id=? AND id_type='pdl_id'", (sid,)))
            if not re.search(r"software|saas|internet|data|analytics|platform", f"{st['sector']} {ind}", re.I):
                return ("not-applicable", 0, "not meaningful for hardware/biotech startups")
            continue
        if kind == "col":
            n = int(st[arg] not in (None, ""))
        elif kind == "suggest":
            n = conn.execute("SELECT COUNT(*) FROM field_suggestions WHERE startup_id=? AND field=? AND status!='rejected'", (sid, arg)).fetchone()[0]
            if n:
                best = max(best, ("proxy", n, f"{n} suggestion(s) for {arg}"), key=lambda x: (x[0] == "filled", x[1]))
                continue
        elif kind == "signal":
            n = conn.execute("SELECT COUNT(*) FROM startup_signals WHERE startup_id=? AND signal_type=?", (sid, arg)).fetchone()[0]
        elif kind == "founders":
            n = conn.execute("SELECT COUNT(DISTINCT person_id) FROM startup_people WHERE startup_id=? AND is_founder=1", (sid,)).fetchone()[0]
        elif kind == "board":
            n = conn.execute("""SELECT COUNT(DISTINCT person_id) FROM startup_people WHERE startup_id=? AND resigned_on IS NULL AND
                                (role='director' OR role LIKE '%board%' OR role LIKE '%chair%')""", (sid,)).fetchone()[0]
        elif kind == "ventures":
            n = conn.execute("""SELECT COUNT(*) FROM person_ventures v JOIN startup_people sp ON sp.person_id=v.person_id
                                WHERE sp.startup_id=? AND sp.is_founder=1""", (sid,)).fetchone()[0]
            if not n and conn.execute("SELECT 1 FROM startup_people WHERE startup_id=? AND is_founder=1", (sid,)).fetchone():
                return ("filled", 0, "founders known; no other ventures found")  # a checked zero is an answer
        elif kind == "education":
            n = conn.execute("""SELECT COUNT(*) FROM people p JOIN startup_people sp ON sp.person_id=p.id
                                WHERE sp.startup_id=? AND sp.is_founder=1 AND p.education IS NOT NULL AND p.education!='[]'""", (sid,)).fetchone()[0]
        elif kind == "xpeers":
            n = conn.execute("SELECT COUNT(*) FROM startup_external_peers WHERE startup_id=?", (sid,)).fetchone()[0]
        elif kind == "peers":
            n = conn.execute("SELECT COUNT(*) FROM startup_peers WHERE startup_id=? AND similarity>=0.1", (sid,)).fetchone()[0]
        elif kind == "peerfunding":
            n = conn.execute("""SELECT COUNT(*) FROM startup_peers p JOIN startup_features f ON f.startup_id=p.peer_id AND f.feature='total_raised_usd'
                                WHERE p.startup_id=? AND p.similarity>=0.1""", (sid,)).fetchone()[0]
        elif kind == "events":
            n = conn.execute("SELECT COUNT(*) FROM funding_events WHERE startup_id=? AND total_shares_after IS NOT NULL", (sid,)).fetchone()[0]
        elif kind == "feature":
            n = conn.execute("SELECT COUNT(*) FROM startup_features WHERE startup_id=? AND feature=? AND value_num IS NOT NULL", (sid, arg)).fetchone()[0]
        elif kind == "jobsnapshots":
            n = conn.execute("""SELECT COUNT(DISTINCT COALESCE(json_extract(details,'$.snapshot'), substr(fetched_at,1,10)))
                                FROM startup_signals WHERE startup_id=? AND signal_type='job'""", (sid,)).fetchone()[0]
            n = n if n >= 2 else 0
        elif kind == "unit":
            n = conn.execute("SELECT COUNT(*) FROM startup_signals WHERE startup_id=? AND unit=?", (sid, arg)).fetchone()[0]
        elif kind == "ext":
            n = conn.execute("SELECT COUNT(*) FROM startup_external_ids WHERE startup_id=? AND id_type=?", (sid, arg)).fetchone()[0]
        elif kind == "rounds":
            n = conn.execute("SELECT COUNT(*) FROM funding_rounds WHERE startup_id=?", (sid,)).fetchone()[0]
        elif kind == "assess":
            n = conn.execute("SELECT COUNT(*) FROM readiness_assessments WHERE startup_id=?", (sid,)).fetchone()[0]
        elif kind == "kpi":
            sql = "SELECT COUNT(*) FROM startup_ocean_kpis WHERE startup_id=? AND evidence_level>0" + (" AND kpi_code LIKE ?" if arg else "")
            n = conn.execute(sql, (sid, f"{arg}%") if arg else (sid,)).fetchone()[0]
        elif kind == "market":
            n = conn.execute("SELECT COUNT(*) FROM market_indicators WHERE geo IN (SELECT ?)", (WB_COUNTRIES.get(st["country"], "?"),)).fetchone()[0]
        if n:
            return ("filled", n, part)
    return best


def build_gaps(conn):
    conn.execute("DELETE FROM startup_parameter_status")
    for sec, sname, item, nm, desc in parse_parameters():
        cov, rule, srcs = COVER.get((sec, item), ("missing", None, None))
        prio = SECTION_PRIORITY.get(sec)
        if sec == "K" and item > 10:
            prio = "P1"
        conn.execute("""INSERT INTO assessment_parameters (section_code, section_name, item_no, name, description, priority, coverage, filled_by, sources)
                        VALUES (?,?,?,?,?,?,?,?,?)
                        ON CONFLICT(section_code, item_no) DO UPDATE SET section_name=excluded.section_name, name=excluded.name,
                          description=excluded.description, priority=excluded.priority, coverage=excluded.coverage,
                          filled_by=excluded.filled_by, sources=excluded.sources""",
                     (sec, sname, item, nm, desc, prio, cov, rule, srcs))
    params = conn.execute("SELECT * FROM assessment_parameters").fetchall()
    for st in conn.execute("SELECT * FROM startups").fetchall():
        for p in params:
            if not p["filled_by"]:
                status, n, det = "not-collectable", 0, "needs founder, VC or paid data"
            else:
                status, n, det = evaluate(conn, p["filled_by"], st)
                if status == "filled" and p["coverage"] == "partial":
                    status = "proxy"
            conn.execute("INSERT INTO startup_parameter_status VALUES (?,?,?,?,?)", (st["id"], p["id"], status, n, det))
    conn.commit()
    write_report(conn)


def report_path() -> Path:
    """GAPS.md next to the DB in use: the tracked copy only when writing to the snapshot itself."""
    db = db_path()
    return HERE / "GAPS.md" if db.resolve() == snapshot_path().resolve() else db.parent / "GAPS.md"


def write_report(conn, path: Path | None = None, source: str | None = None):
    q = lambda sql, *a: conn.execute(sql, a).fetchall()  # noqa: E731
    L = ["# Data gaps: what the database holds vs the VC parameter list\n",
         f"Generated by `Modules/DataAPIs/ingest.py` on {now()} UTC from `{source or _rel(db_path())}`. "
         "Parameters come from [parameters.txt](parameters.txt) sections A–U.\n",
         "- **auto**: filled from seed data or public APIs\n- **partial**: only an indirect proxy is available\n"
         "- **missing**: needs founder-submitted, VC-internal or paid data\n",
         "## 1. Coverage by section\n", "| Section | Priority | Params | auto | partial | missing |", "|---|---|---|---|---|---|"]
    for r in q("""SELECT section_code, section_name, priority, COUNT(*) n, SUM(coverage='auto') a, SUM(coverage='partial') p, SUM(coverage='missing') m
                  FROM assessment_parameters GROUP BY section_code ORDER BY section_code"""):
        L.append(f"| {r['section_code']}. {r['section_name']} | {r['priority'] or ''} | {r['n']} | {r['a']} | {r['p']} | {r['m']} |")
    t = q("SELECT COUNT(*) n, SUM(coverage='auto') a, SUM(coverage='partial') p, SUM(coverage='missing') m FROM assessment_parameters")[0]
    L.append(f"| **Total** | | **{t['n']}** | **{t['a']}** | **{t['p']}** | **{t['m']}** |\n")

    L += ["## 2. Per startup: collectable parameters actually filled\n",
          "Counts only the parameters public data can fill (auto + partial). `empty` = collectable but nothing found yet.\n",
          "| Startup | filled | proxy | empty | n/a | fill rate | patents | papers | news | launches | repos | web history | suggestions |",
          "|---|---|---|---|---|---|---|---|---|---|---|---|---|"]
    for r in q("""SELECT s.id, s.name,
                    SUM(sps.status='filled') f, SUM(sps.status='proxy') p, SUM(sps.status='empty') e, SUM(sps.status='not-applicable') na
                  FROM startups s JOIN startup_parameter_status sps ON sps.startup_id=s.id GROUP BY s.id ORDER BY s.id"""):
        cnt = {k: v for k, v in q("SELECT signal_type, COUNT(*) FROM startup_signals WHERE startup_id=? GROUP BY signal_type", r["id"])}
        sug = q("SELECT COUNT(*) FROM field_suggestions WHERE startup_id=?", r["id"])[0][0]
        tot = r["f"] + r["p"] + r["e"]
        L.append(f"| {r['name']} | {r['f']} | {r['p']} | {r['e']} | {r['na']} | {100 * (r['f'] + r['p']) // tot}% | {cnt.get('patent', 0)} | {cnt.get('paper', 0)} | "
                 f"{cnt.get('news', 0)} | {cnt.get('launch', 0)} | {cnt.get('repo', 0)} | {cnt.get('web_history', 0)} | {sug} |")

    L += ["\n## 3. Collectable but empty (by startup)\n"]
    for r in q("""SELECT s.name, GROUP_CONCAT(p.section_code || p.item_no || ' ' || p.name, '; ') items
                  FROM startup_parameter_status sps JOIN startups s ON s.id=sps.startup_id JOIN assessment_parameters p ON p.id=sps.parameter_id
                  WHERE sps.status='empty' GROUP BY s.id ORDER BY s.id"""):
        L.append(f"- **{r['name']}**: {r['items']}")

    L += ["\n## 4. Suggested values for curated fields (pending review)\n",
          "| Startup | Field | Current | Suggested | Source | Confidence | Evidence |", "|---|---|---|---|---|---|---|"]
    for r in q("""SELECT s.name, f.field, f.current_value, f.value, f.source_name, f.match_confidence, f.evidence
                  FROM field_suggestions f JOIN startups s ON s.id=f.startup_id ORDER BY s.id, f.field, f.match_confidence"""):
        L.append(f"| {r['name']} | {r['field']} | {r['current_value'] or '**(empty)**'} | {r['value']} | {r['source_name']} | {r['match_confidence']} | {r['evidence']} |")

    L += ["\n## 5. P0 parameters that public APIs cannot fill\n",
          "These need founder-submitted data, VC deal-room access or a paid provider.\n"]
    for r in q("""SELECT section_code, section_name, GROUP_CONCAT(item_no || '. ' || name, '; ') items FROM assessment_parameters
                  WHERE coverage='missing' AND priority='P0' GROUP BY section_code ORDER BY section_code"""):
        L.append(f"- **{r['section_code']}. {r['section_name']}**: {r['items']}")

    L += ["\n## 6. Sources not yet contributing\n", "| Source | Access | Last status | Why |", "|---|---|---|---|"]
    for r in q("SELECT name, access, last_status, last_info FROM data_sources WHERE last_status!='ok' ORDER BY access, name"):
        L.append(f"| {r['name']} | {r['access']} | {r['last_status']} | {(r['last_info'] or '').replace('|', '/')[:120]} |")

    L += ["\n## 7. Loaded tables\n", "| Table | Rows |", "|---|---|"]
    for tname in ("startups", "funding_rounds", "raw_fetches", "startup_external_ids", "startup_signals", "field_suggestions",
                  "funding_opportunities", "market_indicators", "assessment_parameters", "startup_parameter_status"):
        L.append(f"| {tname} | {q(f'SELECT COUNT(*) FROM {tname}')[0][0]} |")
    path = path or report_path()
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text("\n".join(L) + "\n")
    print(f"wrote {_rel(path)}")


def _rel(p: Path) -> str:
    try:
        return str(p.resolve().relative_to(REPO))
    except ValueError:  # outside the repository (e.g. a test DB)
        return str(p)


def main(argv):
    conn = open_db()
    if "--gaps-only" not in argv:
        yc, _ = fetch(conn, "yc_oss_companies", None, kind="companies", name="all")
        for st in conn.execute("SELECT * FROM startups ORDER BY id").fetchall():
            print(f"-> {st['name']}")
            ingest_startup(conn, st, yc, use_gdelt="--gdelt" in argv)
        print("-> funding opportunities"); ingest_funding(conn)
        print("-> market indicators"); ingest_market(conn)
    if "--pdl" in argv:
        for st in conn.execute("SELECT * FROM startups ORDER BY id").fetchall():
            print(f"-> pdl {st['name']}")
            ingest_pdl(conn, st)
    if "--uk" in argv:
        for st in conn.execute("SELECT * FROM startups WHERE country='United Kingdom' ORDER BY id").fetchall():
            print(f"-> companies house {st['name']}")
            ingest_companies_house(conn, st)
    if "--serpapi" in argv or "--gaps-only" not in argv:
        for st in conn.execute("SELECT * FROM startups ORDER BY id").fetchall():
            print(f"-> serpapi {st['name']}")
            ingest_serpapi(conn, st)
    build_gaps(conn)
    for r in conn.execute("SELECT 'signals', COUNT(*) FROM startup_signals UNION ALL SELECT 'ext_ids', COUNT(*) FROM startup_external_ids "
                          "UNION ALL SELECT 'suggestions', COUNT(*) FROM field_suggestions UNION ALL SELECT 'opportunities', COUNT(*) FROM funding_opportunities "
                          "UNION ALL SELECT 'market', COUNT(*) FROM market_indicators UNION ALL SELECT 'parameters', COUNT(*) FROM assessment_parameters"):
        print(f"{r[0]:14} {r[1]}")


if __name__ == "__main__":
    main(sys.argv[1:])
