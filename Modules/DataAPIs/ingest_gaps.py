#!/usr/bin/env python3
"""Close remaining public-data gaps: non-UK founders and boards, hiring, competitor universe.

  python3 ingest_gaps.py                    founders (non-UK, via PDL), job boards, BlueInvest peers
  python3 ingest_gaps.py --only=jobs,peers  steps: founders, jobs, peers
  python3 ingest_gaps.py --founders-all     also run PDL founder lookups for UK startups (more credits)

Founders: People Data Labs person search (1 credit per person, max FOUNDER_LIMIT per startup). Only name, role,
dates, venture-like prior roles and education degrees are stored; emails, phone numbers, sex and profile URLs are dropped.
Boards for US startups come from SEC Form D (features.py) and UK ones from Companies House.
"""
from __future__ import annotations

import json
import math
import re
import sys
from datetime import date
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent))
import common  # noqa: E402
import ingest  # noqa: E402
from ingest import domain, fetch, norm, now  # noqa: E402
from ingest_eu import same_company  # noqa: E402

FOUNDER_LIMIT = 5
LEADER_RE = re.compile(r"founder|owner|chief|\bceo\b|\bcto\b|\bcoo\b|\bcso\b|\bcfo\b|managing director|president|chair|board", re.I)
VENTURE_RE = re.compile(r"founder|owner|\bceo\b|chief executive|managing director", re.I)
PROGRAMMES = re.compile(r"entrepreneurs first|y combinator|antler|techstars|founder institute|on deck|venture builder", re.I)  # cohorts, not ventures
BOARD_RE = re.compile(r"chair|board", re.I)


def best_domain(conn, st) -> str | None:
    if st["website"]:
        return domain(st["website"])
    r = conn.execute("""SELECT value FROM field_suggestions WHERE startup_id=? AND field='website' AND status!='rejected'
                        ORDER BY match_confidence='high' DESC, match_confidence='medium' DESC LIMIT 1""", (st["id"],)).fetchone()
    return domain(r[0]) if r else None


def founded_date(conn, st) -> str | None:
    if st["founded_year"]:
        return f"{st['founded_year']}-01-01"
    r = conn.execute("SELECT MIN(value) FROM field_suggestions WHERE startup_id=? AND field='founded_year' AND status!='rejected'", (st["id"],)).fetchone()
    return f"{r[0]}-01-01" if r and r[0] else None


# ---------------------------------------------------------------------------
# Founders, executives and board (PDL)
# ---------------------------------------------------------------------------
def ingest_founders(conn, st):
    sid, dom = st["id"], best_domain(conn, st)
    if not dom:
        return
    # Two precise queries; one OR-query across all nested fields matched founders of *other* companies.
    queries = [  # (A) current leaders at this company, (B) founders who may have left
        (f"SELECT * FROM person WHERE job_company_website='{dom}' AND "
         "(job_title_levels='cxo' OR job_title_levels='owner' OR job_title LIKE '%founder%')", 4),
        (f"SELECT * FROM person WHERE experience.company.website='{dom}' AND experience.title.name LIKE '%founder%'", 2),
    ]
    people, f = {}, None
    for sql, size in queries:
        d, f = fetch(conn, "pdl_person_search", sid, sql=sql, size=size)
        for p in (d or {}).get("data", []) if (d or {}).get("status") == 200 else []:
            people[p.get("id")] = p
    if not people:
        return
    conn.execute("DELETE FROM startup_people WHERE startup_id=? AND source_name='people_data_labs'", (sid,))
    started = founded_date(conn, st)
    for p in people.values():
        exps = p.get("experience") or []
        here = [e for e in exps if (e.get("company") or {}).get("website") == dom or same_company(st["name"], (e.get("company") or {}).get("name") or "")]
        roles = [e for e in here if LEADER_RE.search(((e.get("title") or {}).get("name")) or "")]
        if not roles:
            continue
        name = (p.get("full_name") or "").title()
        edu = [{"school": (e.get("school") or {}).get("name"), "degrees": e.get("degrees") or []} for e in p.get("education") or []]
        conn.execute("""INSERT INTO people (name, pdl_id, education) VALUES (?,?,?)
                        ON CONFLICT(pdl_id) DO UPDATE SET name=excluded.name, education=excluded.education""", (name, p.get("id"), json.dumps(edu)))
        pid = conn.execute("SELECT id FROM people WHERE pdl_id=?", (p.get("id"),)).fetchone()[0]
        for e in roles:
            title = (e.get("title") or {}).get("name") or ""
            start, end = e.get("start_date"), e.get("end_date")
            early = bool(start and started and start[:4] <= str(int(started[:4]) + 1))
            founder = int("founder" in title.lower() or (early and bool(VENTURE_RE.search(title))))
            conn.execute("""INSERT OR REPLACE INTO startup_people (startup_id, person_id, role, is_founder, appointed_on, resigned_on, source_name)
                            VALUES (?,?,?,?,?,?, 'people_data_labs')""", (sid, pid, title, founder, start, end))
        first_start = min((e.get("start_date") or "9999") for e in roles)
        conn.execute("DELETE FROM person_ventures WHERE person_id=? AND source_name='people_data_labs'", (pid,))
        for e in exps:
            if e in here or not VENTURE_RE.search(((e.get("title") or {}).get("name")) or ""):
                continue  # keep venture-like roles only (founder / owner / CEO / MD), not every past job
            if PROGRAMMES.search(((e.get("company") or {}).get("name")) or ""):
                continue
            co = e.get("company") or {}
            conn.execute("""INSERT OR REPLACE INTO person_ventures (person_id, company_number, company_name, company_status, role, appointed_on, resigned_on, source_name)
                            VALUES (?,?,?,NULL,?,?,?, 'people_data_labs')""",
                         (pid, f"pdl:{co.get('id') or norm(co.get('name'))}", (co.get("name") or "").title(), (e.get("title") or {}).get("name"),
                          e.get("start_date"), e.get("end_date")))
    conn.commit()


# ---------------------------------------------------------------------------
# Job boards
# ---------------------------------------------------------------------------
ATS_LINKS = {
    "ashby": r"jobs\.ashbyhq\.com/([\w.-]+)", "greenhouse": r"(?:boards|job-boards)\.greenhouse\.io/([\w.-]+)",
    "lever": r"jobs\.lever\.co/([\w.-]+)", "workable": r"apply\.workable\.com/([\w.-]+)",
    "recruitee": r"([\w-]+)\.recruitee\.com", "personio": r"([\w-]+)\.jobs\.personio\.(?:de|com)",
}
CATEGORY = [("technical", r"engineer|scientist|developer|technician|r&d|research|data|software|hardware|mechanical|electrical|chemist|biolog|lab|naval|robot|firmware|acoustic"),
            ("commercial", r"sales|business development|account|marketing|commercial|customer|partnership|growth"),
            ("operations", r"operation|production|manufactur|supply|logistic|farm|vessel|crew|harvest|quality|procurement|field")]


def job_category(title: str, dept: str | None) -> str:
    text = f"{title} {dept or ''}".lower()
    return next((cat for cat, rx in CATEGORY if re.search(rx, text)), "other")


def ingest_jobs(conn, st):
    sid = st["id"]
    dom = best_domain(conn, st)
    slugs = {norm(st["name"]), re.sub(r"[^a-z0-9]+", "-", st["name"].lower()).strip("-")}
    if dom:
        slugs.add(dom.split(".")[0])
    found: list[tuple[str, str]] = []
    if dom:  # the careers page usually links the ATS directly
        for path in ("", "/careers", "/jobs", "/join-us"):
            try:
                page = common.http(f"https://{dom}{path}", raw=True, headers={"User-Agent": "Mozilla/5.0"})
            except Exception:  # noqa: BLE001
                continue
            for ats, rx in ATS_LINKS.items():
                for slug in re.findall(rx, page):
                    if slug not in ("embed", "www", "api", "js"):
                        found.append((ats, slug.lower()))
    candidates = list(dict.fromkeys(found + [(ats, s) for s in slugs for ats in ATS_LINKS]))
    for ats, slug in candidates:
        try:  # unlogged probe: most guesses 404
            jobs = ingest.SRC["job_boards"].fn(ats=ats, slug=slug)
        except Exception:  # noqa: BLE001
            continue
        if not jobs and (ats, slug) not in found:
            continue
        jobs, f = fetch(conn, "job_boards", sid, ats=ats, slug=slug)  # logged fetch for the board that answered
        conn.execute("DELETE FROM startup_signals WHERE startup_id=? AND source_name='job_boards'", (sid,))
        for j in jobs or []:
            cat = job_category(j["title"] or "", j.get("department"))
            ingest.signal(conn, sid, "job_boards", "job", f"{j['title']} ({j.get('location') or 'n/a'})", j.get("url"), j.get("posted") or now()[:10],
                          details={"ats": ats, "slug": slug, "department": j.get("department"), "category": cat, "location": j.get("location"),
                                   "snapshot": now()[:10]}, conf="high", fetch_id=f)
        conn.execute("""INSERT OR REPLACE INTO startup_external_ids (startup_id, id_type, external_id, source_name, url, match_confidence, fetch_id)
                        VALUES (?, 'job_board', ?, 'job_boards', ?, ?, ?)""",
                     (sid, f"{ats}:{slug}", None, "high" if (ats, slug) in found else "medium", f))
        break
    # Google Jobs postings (serpapi) get a category too, so hiring features can split technical vs commercial
    for r in conn.execute("SELECT id, title, details FROM startup_signals WHERE startup_id=? AND signal_type='job' AND source_name!='job_boards'", (sid,)).fetchall():
        det = json.loads(r["details"] or "{}")
        det["category"] = job_category(r["title"], det.get("department"))
        conn.execute("UPDATE startup_signals SET details=? WHERE id=?", (json.dumps(det), r["id"]))
    conn.commit()


# ---------------------------------------------------------------------------
# Competitor universe from the BlueInvest pipeline
# ---------------------------------------------------------------------------
STOP = set("""the and for with from that this into their our are its has have been which made make based using company companies
solution solutions project projects product products system systems platform innovative innovation sustainable sustainability
market markets business new world first more than also will can all through over use used develop developing development
technology technologies services service blue economy ocean oceans marine sea""".split())


def tokens(text: str) -> set[str]:
    return {w.rstrip("s") for w in re.findall(r"[a-z]{4,}", (text or "").lower()) if w not in STOP}


def ingest_peers(conn, top_k=10, min_sim=0.05):
    profiles = conn.execute("SELECT other_id, name, summary, sector, trl, url, startup_id FROM blueinvest_profiles").fetchall()
    if not profiles:
        return
    startups = conn.execute("SELECT * FROM startups").fetchall()
    docs = {("bi", p["other_id"]): tokens(f"{p['name']} {p['summary']}") | ({f"sector:{norm(p['sector'])}"} if p["sector"] else set()) for p in profiles}
    for st in startups:
        sector = conn.execute("SELECT sector FROM blueinvest_profiles WHERE startup_id=? LIMIT 1", (st["id"],)).fetchone()
        docs[("st", st["id"])] = tokens(f"{st['tagline']} {st['description']} {st['sector']}") | ({f"sector:{norm(sector[0])}"} if sector else set())
    df: dict[str, int] = {}
    for toks in docs.values():
        for t in toks:
            df[t] = df.get(t, 0) + 1
    n = len(docs)
    idf = {t: math.log(n / c) for t, c in df.items()}
    norm2 = {k: math.sqrt(sum(idf[t] ** 2 for t in v)) or 1.0 for k, v in docs.items()}
    conn.execute("DELETE FROM startup_external_peers WHERE source='blueinvest'")
    for st in startups:
        a = docs[("st", st["id"])]
        scored = []
        for p in profiles:
            if p["startup_id"] == st["id"]:
                continue  # its own profile
            b = docs[("bi", p["other_id"])]
            shared = a & b
            if not shared:
                continue
            sim = sum(idf[t] ** 2 for t in shared) / (norm2[("st", st["id"])] * norm2[("bi", p["other_id"])])
            if sim >= min_sim:
                scored.append((sim, p, sorted(shared, key=lambda t: -idf[t])[:8]))
        for sim, p, shared in sorted(scored, key=lambda x: -x[0])[:top_k]:
            conn.execute("INSERT INTO startup_external_peers VALUES (?,?,?,?,?,?,?,?,?)",
                         (st["id"], "blueinvest", str(p["other_id"]), p["name"], round(sim, 4), json.dumps(shared), p["trl"], p["sector"], p["url"]))
    conn.commit()


def main(argv):
    only = set(next((a.split("=", 1)[1] for a in argv if a.startswith("--only=")), "founders,jobs,peers").split(","))
    conn = ingest.open_db()
    for st in conn.execute("SELECT * FROM startups ORDER BY id").fetchall():
        print(f"-> {st['name']}")
        if "founders" in only:
            uk_founders = conn.execute("SELECT 1 FROM startup_people WHERE startup_id=? AND source_name='uk_companies_house_company' AND is_founder=1",
                                       (st["id"],)).fetchone()
            if not uk_founders or "--founders-all" in argv:
                ingest_founders(conn, st)
        if "jobs" in only:
            ingest_jobs(conn, st)
    if "peers" in only:
        ingest_peers(conn)
    conn.execute("DELETE FROM people WHERE id NOT IN (SELECT person_id FROM startup_people)")  # drop people no longer linked
    conn.commit()
    q = lambda s: conn.execute(s).fetchone()[0]  # noqa: E731
    people = q("SELECT COUNT(*) FROM startup_people WHERE source_name='people_data_labs'")
    jobs = q("SELECT COUNT(*) FROM startup_signals WHERE signal_type='job'")
    peers = q("SELECT COUNT(*) FROM startup_external_peers")
    print(f"PDL people: {people}, job postings: {jobs}, external peers: {peers}")


if __name__ == "__main__":
    main(sys.argv[1:])
