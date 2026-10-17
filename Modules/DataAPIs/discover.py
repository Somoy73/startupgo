#!/usr/bin/env python3
"""Add startups to the runtime DB from the EU BlueInvest Project Pipeline.

  python3 discover.py --count 25                     EU startups, TRL >= 6, ocean-tech sectors
  python3 discover.py --count 25 --min-trl 5 --countries Finland,Sweden
  python3 discover.py --dry-run                      show what would be added

Candidates are taken round-robin across sectors (highest TRL first); each one's BlueInvest detail page gives the
company, country and website. Kept: companies in the chosen countries with a website, not research institutes,
universities, public bodies or duplicates of startups already in the DB. New rows go to the runtime DB only, with
pipeline_stage 'sourced' and stage 'unknown'. No readiness assessment is invented: scores come later (Agent or analyst).
Run refresh.py afterwards to enrich them.
"""
from __future__ import annotations

import argparse
import re
import sys
import time
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent))
import ingest  # noqa: E402
import ingest_eu  # noqa: E402
from ingest import domain, ext_id, fetch, norm  # noqa: E402

EU27 = ("Austria", "Belgium", "Bulgaria", "Croatia", "Cyprus", "Czechia", "Czech Republic", "Denmark", "Estonia", "Finland",
        "France", "Germany", "Greece", "Hungary", "Ireland", "Italy", "Latvia", "Lithuania", "Luxembourg", "Malta",
        "Netherlands", "Poland", "Portugal", "Romania", "Slovakia", "Slovenia", "Spain", "Sweden")
SECTORS = ("Aquaculture", "Blue biotechnology", "Blue renewable energy", "Shipping & ports", "Ocean pollution & water management",
           "Blue tech and ocean observation", "Coastal and environmental protection and regeneration", "Shipbuilding & Refit", "Fisheries")
NOT_A_STARTUP = re.compile(r"universit|institut|instituto|research cent|centre for|center for|foundation|fundaci|association|asociaci|"
                           r"council|municipal|ministry|agency|authority|cluster|consortium|federation|chamber of|"
                           r"\bAZTI\b|\bCSIC\b|\bCNR\b|fraunhofer|ifremer|\bport of\b", re.I)


def slugify(name: str, taken: set[str]) -> str:
    base = re.sub(r"[^a-z0-9]+", "-", name.lower()).strip("-")[:50] or "startup"
    slug, n = base, 2
    while slug in taken:
        slug, n = f"{base}-{n}", n + 1
    taken.add(slug)
    return slug


def tagline(profile_name: str, company: str, summary: str | None) -> str:
    if profile_name and norm(profile_name) != norm(company) and len(profile_name) <= 140:
        return profile_name.strip().strip("'\"")
    first = re.split(r"(?<=[.!?])\s", (summary or "").strip(), maxsplit=1)[0]
    return (first or profile_name or company)[:180]


def candidates(conn, min_trl: int, sectors: tuple[str, ...]) -> list:
    rows = conn.execute(f"""SELECT * FROM blueinvest_profiles WHERE startup_id IS NULL AND trl >= ? AND sector IN ({','.join('?' * len(sectors))})
                            ORDER BY trl DESC, other_id""", (min_trl, *sectors)).fetchall()
    by_sector: dict[str, list] = {}
    for r in rows:
        by_sector.setdefault(r["sector"], []).append(r)
    ordered, i = [], 0  # round-robin so one sector does not fill the list
    while any(i < len(v) for v in by_sector.values()):
        ordered += [v[i] for v in by_sector.values() if i < len(v)]
        i += 1
    return ordered


def discover(count: int = 25, min_trl: int = 6, countries: tuple[str, ...] = EU27, sectors: tuple[str, ...] = SECTORS,
             max_details: int = 200, dry_run: bool = False) -> list[dict]:
    conn = ingest.open_db()
    if not conn.execute("SELECT 1 FROM blueinvest_profiles LIMIT 1").fetchone():
        ingest_eu.crawl_blueinvest(conn)
    have_domains = {domain(r[0]) for r in conn.execute("SELECT website FROM startups WHERE website IS NOT NULL")}
    taken = {r[0] for r in conn.execute("SELECT slug FROM startups")}
    picked, fetched = [], 0
    for c in candidates(conn, min_trl, sectors):
        if len(picked) >= count or fetched >= max_details:
            break
        if NOT_A_STARTUP.search(c["name"]):
            continue
        page, f = fetch(conn, "blueinvest_profile", None, other_id=c["other_id"])
        fetched += 1
        time.sleep(1)  # polite to the BlueInvest site
        if not isinstance(page, str):
            continue
        d = ingest_eu.parse_profile(page)
        conn.execute("""UPDATE blueinvest_profiles SET company=?, country=?, financial_needs=?, funding_sought_eur=?, website=? WHERE other_id=?""",
                     (d.get("company"), d.get("country"), d.get("financial_needs"), d.get("funding_sought_eur"), d.get("website"), c["other_id"]))
        conn.commit()
        company, country, site = (d.get("company") or "").strip(), (d.get("country") or "").strip(), d.get("website")
        if len(company) <= 3 and len(c["name"]) > len(company):  # profile parse glitch (e.g. "Aa" for "PaRAS Aqua Oy")
            company = c["name"].strip()
        if site and re.match(r"https?://ww\.", site):  # "ww." typo in some profiles
            site = re.sub(r"//ww\.", "//www.", site, count=1)
        dom = domain(site) if site else None
        if not (company and site and dom) or country not in countries or NOT_A_STARTUP.search(company) or dom in have_domains:
            continue
        have_domains.add(dom)
        row = {"other_id": c["other_id"], "name": company, "country": country, "website": f"https://{dom}", "sector": c["sector"],
               "trl": c["trl"], "tagline": tagline(c["name"], company, c["summary"]), "description": (c["summary"] or c["name"])[:2000],
               "profile_url": c["url"]}
        picked.append(row)
        print(f"  + {company} ({country}, {c['sector']}, TRL {c['trl']}) {row['website']}")
    print(f"{len(picked)} picked after {fetched} detail pages")
    if dry_run:
        return picked
    for row in picked:
        slug = slugify(row["name"], taken)
        sid = conn.execute("""INSERT INTO startups (slug, name, tagline, description, sector, country, website, stage, pipeline_stage)
                              VALUES (?,?,?,?,?,?,?, 'unknown', 'sourced')""",
                           (slug, row["name"], row["tagline"], row["description"], row["sector"], row["country"], row["website"])).lastrowid
        conn.execute("UPDATE blueinvest_profiles SET startup_id=? WHERE other_id=?", (sid, row["other_id"]))
        conn.execute("INSERT INTO sources (startup_id, title, url) VALUES (?,?,?)", (sid, f"BlueInvest Project Pipeline: {row['name']}", row["profile_url"]))
        ext_id(conn, sid, "blueinvest_profile", row["other_id"], "blueinvest_profile", row["profile_url"],
               {"name": row["name"], "country": row["country"], "sector": row["sector"]}, "high", None)
        row["slug"], row["id"] = slug, sid
    conn.commit()
    print(f"added {len(picked)} startups to {ingest._rel(ingest.db_path())}; run `refresh.py` to enrich them")
    return picked


def main(argv=None):
    p = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    p.add_argument("--count", type=int, default=25)
    p.add_argument("--min-trl", type=int, default=6)
    p.add_argument("--countries", help="comma-separated (default: EU-27)")
    p.add_argument("--max-details", type=int, default=200, help="cap on BlueInvest detail pages fetched")
    p.add_argument("--dry-run", action="store_true")
    a = p.parse_args(argv)
    countries = tuple(x.strip() for x in a.countries.split(",")) if a.countries else EU27
    discover(a.count, a.min_trl, countries, max_details=a.max_details, dry_run=a.dry_run)


if __name__ == "__main__":
    main()
