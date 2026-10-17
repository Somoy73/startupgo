#!/usr/bin/env python3
"""Build the unified 3-table model (entities, facts, assessments) from the pipeline's tables.

  python3 unify.py                 rebuild entities / facts / assessments in the runtime DB
  python3 unify.py --preview PATH  also write a copy of the DB that has ONLY the 3 tables, plus views named like
                                   main's tables (startups, readiness_assessments, funding_rounds, ...) for reading
  python3 unify.py --sql PATH      also write that copy's schema (3 tables + views) as SQL: DB/unified.sql, which the
                                   Backend applies to DB/startupgo_unified.db on start

Facts use the Agent's fact format (Modules/Agent/startup_agent/facts.py): section A-J and field names from its spec,
values in its vocabulary, source_type / status / confidence by its rules (independent sources verify, the startup's
own material claims). Fields the Agent has no slot for go to section Api. Facts and assessments written by the Agent
itself (source_name / engine 'agent') are kept across rebuilds; everything else is rebuilt from the source tables.
"""
from __future__ import annotations

import argparse
import json
import re
import sqlite3
import sys
from datetime import date, datetime, timezone
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent))
import ingest  # noqa: E402
from ingest import domain, norm  # noqa: E402

AGENT_SOURCE = "agent"
REBUILT_ENGINES = ("seed-estimate", "analyst", "startupgo-pipeline")
SOURCE_TYPE = {  # pipeline source -> Agent source type (vocab.SOURCE_TYPES)
    "uk_companies_house_company": "registry", "uk_companies_house": "registry", "gleif_lei": "registry",
    "fr_recherche_entreprises": "registry", "no_brreg": "registry", "sec_edgar_fulltext_formD": "registry",
    "sec_form_d": "registry", "sec_form_d_document": "registry", "uk_sh01": "registry", "uk_companies_house_officer": "registry",
    "cordis_projects": "eu_projects", "eu_sedia_calls": "grant_db", "grants_gov": "grant_db", "ukri_gateway_to_research": "grant_db",
    "ted_eu_tenders": "grant_db", "serpapi_google_patents": "patent", "google_patents_xhr": "patent", "google_patents_page": "patent",
    "google_news_rss": "news", "gdelt_doc": "news", "hn_algolia": "news", "funding_rounds": "news",
    "jina_reader": "website", "blueinvest_profile": "website", "job_boards": "website", "serpapi_google_jobs": "website",
    "serpapi_google": "website",
}  # anything else (PDL, YC, Wikidata, OpenAlex, GitHub, Wayback, seed, analyst) -> "manual"
BASE_CONFIDENCE = {"registry": 0.95, "grant_db": 0.95, "eu_projects": 0.9, "patent": 0.9, "manual": 0.9, "news": 0.8,
                   "website": 0.7, "pitch_deck": 0.7}  # same as the Agent's SOURCE_CONFIDENCE
INDEPENDENT = {"registry", "grant_db", "eu_projects", "patent", "news"}
MATCH_FACTOR = {"high": 1.0, "medium": 0.85, "low": 0.6}
BLUE_SECTOR = {  # BlueInvest / curated sector text -> vocab.BLUE_SECTORS
    "aquaculture": "aquaculture", "blue biotechnology": "blue_biotechnology", "blue renewable energy": "blue_renewable_energy",
    "blue tech and ocean observation": "blue_tech_and_ocean_observation", "ocean data": "blue_tech_and_ocean_observation",
    "coastal and marine tourism": "coastal_and_maritime_tourism", "fisheries": "fisheries",
    "coastal and environmental protection and regeneration": "environmental_protection_and_regeneration",
    "habitat restoration": "environmental_protection_and_regeneration", "shipbuilding & refit": "shipbuilding_and_refit",
    "shipping & ports": "shipping_and_ports", "shipping decarbonisation": "shipping_and_ports",
    "ocean pollution & water management": "water_management", "ocean cleanup": "water_management",
}
ROUND_STAGE = {"pre-seed": "pre_seed", "pre_seed": "pre_seed", "seed": "seed", "series-a": "series_a", "series_a": "series_a",
               "series-b": "series_b_plus", "series-c+": "series_b_plus", "series_b_plus": "series_b_plus", "growth": "series_b_plus"}
COMPANY_STATUS = {"active": "active", "liquidation": "liquidation", "dissolved": "dissolved", "closed": "dissolved", "bankrupt": "bankrupt"}
TRL_TO_DEV_STAGE = {1: "concept", 2: "concept", 3: "lab_proof", 4: "prototype_lab", 5: "prototype_relevant_env",
                    6: "prototype_relevant_env", 7: "demo_operational_env", 8: "qualified_system", 9: "commercial_operation"}
NEWS_TYPE = [("funding", r"rais|fund|invest|round|grant|capital"), ("pilot", r"pilot|trial|deploy|test"),
             ("partnership", r"partner|collaborat|agreement|contract|deal"), ("award", r"award|prize|win|winner"),
             ("hire", r"hire|appoint|join|ceo|cto")]
TECHNICAL_ROLE = re.compile(r"engineer|scientist|technolog|\bcto\b|chief technology|research|chemist|biolog|physic|r&d|developer|naval", re.I)


def employee_range(n: float | None) -> str | None:
    if n is None:
        return None
    return "1-9" if n < 10 else "10-49" if n < 50 else "50-249" if n < 250 else "250+"


def news_type(title: str) -> str:
    return next((t for t, rx in NEWS_TYPE if re.search(rx, title or "", re.I)), "other")


def _j(v):
    return json.loads(v) if v else {}


class Builder:
    def __init__(self, conn: sqlite3.Connection):
        self.conn = conn
        self.seen: set[str] = set()
        self.today = datetime.now(timezone.utc).strftime("%Y-%m-%d")

    # -- entities ----------------------------------------------------------------------------------------------
    def entity(self, key: str, kind: str, name: str, entity_id: int | None = None, **cols) -> int:
        self.seen.add(key)
        cols = {k: v for k, v in cols.items() if v is not None}
        row = self.conn.execute("SELECT id FROM entities WHERE key=?", (key,)).fetchone()
        if row:
            sets = ", ".join(f"{k}=?" for k in ("kind", "name", *cols)) + ", updated_at=datetime('now')"
            self.conn.execute(f"UPDATE entities SET {sets} WHERE id=?", (kind, name, *cols.values(), row[0]))
            return row[0]
        if entity_id is None:  # non-startup entities get ids from 100000, so startup ids stay the startup ids
            entity_id = max(self.conn.execute("SELECT COALESCE(MAX(id), 0) FROM entities").fetchone()[0], 99999) + 1
        names = ["id", "key", "kind", "name", *cols]
        self.conn.execute(f"INSERT INTO entities ({', '.join(names)}) VALUES ({', '.join('?' * len(names))})",
                          (entity_id, key, kind, name, *cols.values()))
        return entity_id

    # -- facts -------------------------------------------------------------------------------------------------
    def fact(self, entity_id: int, section: str, field: str, value, source_name: str, *, evidence: str | None = None,
             url: str | None = None, observed: str | None = None, retrieved: str | None = None, match: str = "high",
             status: str | None = None, related: int | None = None, source_type: str | None = None) -> None:
        stype = source_type or SOURCE_TYPE.get(source_name, "manual")
        conf = round(BASE_CONFIDENCE.get(stype, 0.5) * MATCH_FACTOR.get(match or "high", 0.6), 2)
        status = status or ("verified" if stype in INDEPENDENT and match != "low" else "claimed")
        self.conn.execute("""INSERT INTO facts (entity_id, section, field, value, related_entity_id, evidence, source_url, source_type,
                                                source_name, status, confidence, retrieved_at, observed_on)
                             VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?)""",
                          (entity_id, section, field, json.dumps(value, ensure_ascii=False, default=str), related,
                           (evidence or (value if isinstance(value, str) else json.dumps(value, ensure_ascii=False, default=str)))[:2000],
                           url, stype, source_name, status, conf, (retrieved or self.today)[:10], observed))


# ---------------------------------------------------------------------------------------------------------------
def build(conn: sqlite3.Connection) -> dict[str, int]:
    """Rebuild everything derived from the pipeline tables; keeps the Agent's own facts and assessments."""
    conn.execute("PRAGMA foreign_keys = ON")
    conn.execute("DELETE FROM facts WHERE source_name != ?", (AGENT_SOURCE,))
    conn.execute(f"DELETE FROM assessments WHERE engine IN ({','.join('?' * len(REBUILT_ENGINES))})", REBUILT_ENGINES)
    b = Builder(conn)
    investors = _investors(b)
    people = _people(b)
    for st in conn.execute("SELECT * FROM startups ORDER BY id").fetchall():
        _startup(b, st, investors, people)
    _candidates(b)
    _funding_calls(b)
    _assessments(b)
    # entities no longer in any source and not touched by the Agent
    for (eid, key) in conn.execute("SELECT id, key FROM entities").fetchall():
        if key not in b.seen and not conn.execute("SELECT 1 FROM facts WHERE entity_id=? UNION SELECT 1 FROM assessments WHERE entity_id=?",
                                                  (eid, eid)).fetchone():
            conn.execute("DELETE FROM entities WHERE id=?", (eid,))
    conn.commit()
    q = lambda s: conn.execute(s).fetchone()[0]  # noqa: E731
    return {"entities": q("SELECT COUNT(*) FROM entities"), "facts": q("SELECT COUNT(*) FROM facts"),
            "assessments": q("SELECT COUNT(*) FROM assessments")}


def _investors(b: Builder) -> dict[int, int]:
    out = {}
    for r in b.conn.execute("SELECT * FROM investors").fetchall():
        eid = b.entity(f"investor:{norm(r['name'])}", "investor", r["name"])
        out[r["id"]] = eid
        b.fact(eid, "Api", "investor_profile", {"kind": r["kind"], "tier_score": r["tier_score"]}, "investor_tiers",
               evidence="Analyst-curated tier (investor_tiers.json)", status="claimed")
    return out


def _people(b: Builder) -> dict[int, int]:
    out = {}
    for p in b.conn.execute("SELECT * FROM people").fetchall():
        key = f"person:ch:{p['ch_officer_id']}" if p["ch_officer_id"] else f"person:pdl:{p['pdl_id']}" if p["pdl_id"] else f"person:name:{norm(p['name'])}"
        eid = b.entity(key, "person", p["name"], country=p["country_of_residence"])
        out[p["id"]] = eid
        if p["education"] and p["education"] != "[]":
            b.fact(eid, "Api", "education", _j(p["education"]), "people_data_labs", evidence="PDL education (degree level and school)")
        for v in b.conn.execute("SELECT * FROM person_ventures WHERE person_id=?", (p["id"],)):
            b.fact(eid, "Api", "venture", {"company": v["company_name"], "company_number": v["company_number"], "status": v["company_status"],
                                         "role": v["role"], "from": v["appointed_on"], "to": v["resigned_on"]}, v["source_name"],
                   evidence=f"{v['role']} at {v['company_name']} from {v['appointed_on']}", observed=v["appointed_on"])
    return out


def _startup(b: Builder, st: sqlite3.Row, investors: dict[int, int], people: dict[int, int]) -> None:
    c, sid = b.conn, st["id"]
    ext = {r["id_type"]: r for r in c.execute("SELECT * FROM startup_external_ids WHERE startup_id=?", (sid,))}
    bi = c.execute("SELECT * FROM blueinvest_profiles WHERE startup_id=? ORDER BY trl DESC LIMIT 1", (sid,)).fetchone()
    blue = BLUE_SECTOR.get((bi["sector"] if bi and bi["sector"] else st["sector"] or "").lower(), "other")
    cordis = _j(ext["cordis_org"]["details"]) if "cordis_org" in ext else {}
    eid = b.entity(f"startup:{st['slug']}", "startup", st["name"], entity_id=sid, slug=st["slug"], website=st["website"],
                   domain=domain(st["website"]), country=st["country"], city=st["city"], sector=st["sector"], blue_sector=blue,
                   tagline=st["tagline"], description=st["description"], founded_year=st["founded_year"], stage=st["stage"],
                   pipeline_stage=st["pipeline_stage"],
                   company_number=ext["company_number"]["external_id"] if "company_number" in ext else None,
                   lei=ext["lei"]["external_id"] if "lei" in ext else None, vat=cordis.get("vat"),
                   cordis_id=ext["cordis_org"]["external_id"] if "cordis_org" in ext else None,
                   blueinvest_id=ext["blueinvest_profile"]["external_id"] if "blueinvest_profile" in ext else None,
                   pdl_id=ext["pdl_id"]["external_id"] if "pdl_id" in ext else None,
                   sec_cik=ext["sec_cik"]["external_id"] if "sec_cik" in ext else None)
    f = lambda *a, **k: b.fact(eid, *a, **k)  # noqa: E731

    # A. identity and registry ----------------------------------------------------------------------------------
    if st["founded_year"]:
        f("A", "founded_date", str(st["founded_year"]), "seed", evidence="Curated founding year")
    for r in c.execute("SELECT * FROM field_suggestions WHERE startup_id=? AND status!='rejected'", (sid,)):
        field = {"founded_year": "founded_date", "city": "city"}.get(r["field"])
        if field:
            f("A", field, r["value"], r["source_name"], evidence=r["evidence"], match=r["match_confidence"])
        elif r["field"] == "website":
            f("Api", "website_candidate", r["value"], r["source_name"], evidence=r["evidence"], match=r["match_confidence"])
    for id_type, r in ext.items():
        d = _j(r["details"])
        if id_type in ("company_number", "siren", "no_orgnr", "lei"):
            f("A", "business_id", r["external_id"], r["source_name"], url=r["url"], match=r["match_confidence"],
              evidence=f"{id_type} {r['external_id']} ({d.get('company_name') or d.get('legal_name') or ''})")
            created = d.get("date_of_creation") or d.get("registered_on")
            if created:
                f("A", "founded_date", created[:10], r["source_name"], url=r["url"], match=r["match_confidence"],
                  evidence=f"{id_type} registration date {created[:10]}", observed=created[:10])
            raw_status = (d.get("status") or "").lower()
            if raw_status:
                if raw_status in COMPANY_STATUS:
                    f("A", "status", COMPANY_STATUS[raw_status], r["source_name"], url=r["url"], match=r["match_confidence"],
                      evidence=f"registry status: {d.get('status')}")
                f("Api", "registry_status", raw_status, r["source_name"], url=r["url"], match=r["match_confidence"],
                  evidence=f"registry status: {d.get('status')}")  # keeps values the Agent vocabulary lacks (administration)
            if d.get("type") in ("ltd", "private-limited-guarant-nsc", "private-unlimited"):
                f("A", "legal_form", "limited_company", r["source_name"], url=r["url"], evidence=f"company type {d['type']}")
            elif d.get("type") == "plc":
                f("A", "legal_form", "public_limited_company", r["source_name"], url=r["url"], evidence="company type plc")
            for code in d.get("sic_codes") or []:
                f("A", "industry_code", code, r["source_name"], url=r["url"], evidence=f"SIC {code}")
            if d.get("naf") or d.get("nace"):
                f("A", "industry_code", d.get("naf") or d.get("nace"), r["source_name"], url=r["url"], evidence=f"industry code {d.get('naf') or d.get('nace')}")
        elif id_type == "yc_slug":
            batch = d.get("batch") or ""
            year = re.search(r"(20\d\d)", batch)
            f("G", "accelerators", {"programme": f"Y Combinator {batch}".strip(), "year": int(year.group(1)) if year else None},
              r["source_name"], url=r["url"], evidence=f"YC batch {batch}")
    for s in c.execute("SELECT * FROM startup_signals WHERE startup_id=? AND unit IN ('employees','revenue_eur') ORDER BY observed_on", (sid,)):
        if s["unit"] == "employees" and s["value"] is not None:
            f("F", "team_size", int(s["value"]), s["source_name"], evidence=s["title"], url=s["url"], observed=s["observed_on"], match=s["match_confidence"])
            f("A", "employee_range", employee_range(s["value"]), s["source_name"], evidence=s["title"], url=s["url"], match=s["match_confidence"])
        elif s["unit"] == "revenue_eur" and s["value"]:
            f("A", "revenue_last_fy", s["value"], s["source_name"], evidence=s["title"], url=s["url"], observed=s["observed_on"])

    # B. blue-economy profile -------------------------------------------------------------------------------------
    f("B", "blue_sector", blue, "blueinvest_profile" if bi else "seed", evidence=f"sector: {bi['sector'] if bi else st['sector']}",
      url=bi["url"] if bi else None, status="inferred" if not bi else None)
    f("B", "solution_summary", st["tagline"], "seed", evidence=st["tagline"])
    if bi and bi["summary"]:
        f("Api", "blueinvest_summary", bi["summary"], "blueinvest_profile", url=bi["url"])

    # C. technology ---------------------------------------------------------------------------------------------
    for s in c.execute("SELECT * FROM startup_signals WHERE startup_id=? AND signal_type='patent'", (sid,)):
        d, number = _j(s["details"]), s["title"].split(":")[0].strip()
        year = (s["observed_on"] or "")[:4]
        f("C", "patents", {"number": number, "title": s["title"].split(":", 1)[-1].strip(), "year": int(year) if year.isdigit() else None,
                           "legal_status": d.get("legal_status"), "granted": d.get("grant_date"), "ocean_groups": d.get("ocean_groups")},
          s["source_name"], evidence=s["title"], url=s["url"], observed=s["observed_on"], match=s["match_confidence"])
    for s in c.execute("SELECT * FROM startup_signals WHERE startup_id=? AND unit='trl'", (sid,)):
        trl = int(s["value"])
        f("C", "dev_stage", TRL_TO_DEV_STAGE[trl], s["source_name"], url=s["url"], match=s["match_confidence"],
          evidence=f"Self-reported {_j(s['details']).get('trl_text') or f'TRL {trl}'} (BlueInvest)")
    for s in c.execute("SELECT * FROM startup_signals WHERE startup_id=? AND signal_type='paper'", (sid,)):
        f("Api", "research_paper", {"title": s["title"], "year": s["observed_on"], "citations": s["value"]}, s["source_name"],
          url=s["url"], match=s["match_confidence"], status="inferred")  # mentions, not authorship

    # E. ocean impact (Navigator KPI evidence -> Agent impact fields) -------------------------------------------------
    for k in c.execute("SELECT * FROM startup_ocean_kpis WHERE startup_id=?", (sid,)):
        src, kw = ("funding_rounds" if k["source_url"] else "seed"), {"url": k["source_url"], "evidence": k["claim"]}
        f("Api", "navigator_kpi", {"kpi": k["kpi_code"], "level": k["evidence_level"], "claim": k["claim"]}, src, status="claimed", **kw)
        level = k["evidence_level"]
        if level >= 1:
            f("E", "impact_claim", k["claim"], src, status="claimed", **kw)
        if level >= 2:
            f("E", "impact_pathway", k["claim"], src, status="claimed", **kw)
        if level >= 3:
            f("E", "impact_measured", {"metric": k["kpi_code"], "value": k["claim"], "period": None}, src, status="claimed", **kw)
        if level >= 4:
            f("E", "impact_verified_by", "third party (per assessment)", src, **kw)

    # F. team ---------------------------------------------------------------------------------------------------
    created = c.execute("SELECT MIN(value) FROM field_suggestions WHERE startup_id=? AND field='founded_year'", (sid,)).fetchone()[0]
    start = f"{st['founded_year'] or created or '9999'}-01-01"
    seen_founders, seen_board = set(), set()
    for p in c.execute("""SELECT sp.*, p.name FROM startup_people sp JOIN people p ON p.id=sp.person_id WHERE sp.startup_id=?
                          ORDER BY sp.is_founder DESC, sp.appointed_on""", (sid,)):
        pid = people.get(p["person_id"])
        if p["is_founder"] and p["person_id"] not in seen_founders:
            seen_founders.add(p["person_id"])
            prior = c.execute("SELECT COUNT(*) FROM person_ventures WHERE person_id=? AND appointed_on < ?", (p["person_id"], start)).fetchone()[0]
            f("F", "founders", {"name": p["name"], "role": p["role"], "technical": bool(TECHNICAL_ROLE.search(p["role"] or "")) or None,
                                "prior_startup": bool(prior) or None, "active": not p["resigned_on"]},
              p["source_name"], evidence=f"{p['name']}: {p['role']} from {p['appointed_on']}", observed=p["appointed_on"], related=pid)
        elif not p["is_founder"] and not p["resigned_on"] and re.search(r"director|board|chair", p["role"] or "", re.I) \
                and p["person_id"] not in seen_board:
            seen_board.add(p["person_id"])
            f("F", "advisors_board", {"name": p["name"], "background": p["role"]}, p["source_name"],
              evidence=f"{p['name']}: {p['role']}", observed=p["appointed_on"], related=pid)

    # G. funding ------------------------------------------------------------------------------------------------
    for r in c.execute("SELECT * FROM funding_rounds WHERE startup_id=?", (sid,)):
        raw = {"round_type": r["round_type"], "amount": r["amount"], "currency": r["currency"], "announced_on": r["announced_on"],
               "lead_investors": r["lead_investors"], "notes": r["notes"]}
        status = None if r["source_url"] else "claimed"
        if r["round_type"] == "grant":
            year = (r["announced_on"] or "")[:4]
            f("G", "grants", {**raw, "funder": r["lead_investors"], "programme": r["notes"], "year": int(year) if year.isdigit() else None},
              "funding_rounds", url=r["source_url"], observed=r["announced_on"], evidence=r["notes"] or r["lead_investors"], status=status)
        else:
            f("G", "equity_rounds", {**raw, "date": r["announced_on"], "stage": ROUND_STAGE.get(r["round_type"], "other"),
                                     "investors": [x.strip() for x in (r["lead_investors"] or "").split(";") if x.strip()]},
              "funding_rounds", url=r["source_url"], observed=r["announced_on"], status=status,
              evidence=f"{r['round_type']} {r['amount'] or 'undisclosed'} {r['currency'] or ''} ({r['lead_investors'] or ''})")
    for g in c.execute("SELECT * FROM eu_grants WHERE startup_id=?", (sid,)):
        f("G", "grants", {"funder": "European Commission", "programme": f"{g['framework'] or ''} {g['acronym'] or ''}".strip(),
                          "amount": g["ec_contribution"], "currency": "EUR", "year": int(g["start_date"][:4]) if g["start_date"] else None,
                          "role": g["role"], "project_id": g["project_id"], "eic": bool(g["is_eic"]), "mission_ocean": bool(g["is_mission_ocean"])},
          "cordis_projects", url=g["url"], observed=g["start_date"], evidence=f"{g['acronym']}: {g['role']}, EU contribution {g['ec_contribution']}")
    offerings: dict[str, sqlite3.Row] = {}
    for e in c.execute("SELECT * FROM funding_events WHERE startup_id=? AND event_type='form_d'", (sid,)):
        prev = offerings.get(e["event_date"])
        if not prev or (_j(e["details"]).get("filed_on") or "") >= (_j(prev["details"]).get("filed_on") or ""):
            offerings[e["event_date"]] = e  # amendments replace the original filing
    for e in offerings.values():
        f("G", "equity_rounds", {"date": e["event_date"], "stage": "other", "amount": e["amount"], "currency": "USD",
                                 "investors": [], "investor_count": e["investor_count"]}, "sec_form_d", url=e["source_url"],
          observed=e["event_date"], evidence=f"Form D offering, first sale {e['event_date']}: {e['amount']} USD sold to {e['investor_count']} investors")
    for grp in priced_rounds(c.execute("SELECT * FROM funding_events WHERE startup_id=? AND event_type='priced_allotment' ORDER BY event_date",
                                       (sid,)).fetchall()):
        f("G", "equity_rounds", {"date": grp["start"], "stage": "other", "amount": round(grp["amount"], 2), "currency": grp["currency"],
                                 "investors": [], "price_per_share": grp["price"], "allotments": grp["n"]}, "uk_sh01", url=grp["url"],
          observed=grp["start"], evidence=f"{grp['n']} SH01 allotment(s) at {grp['currency']} {grp['price']}/share from {grp['start']}, {grp['currency']} {grp['amount']:,.0f}")
    for s in c.execute("SELECT * FROM startup_signals WHERE startup_id=? AND unit IN ('usd_raised','eur_sought')", (sid,)):
        if s["unit"] == "usd_raised":
            f("G", "total_raised", s["value"], s["source_name"], evidence=s["title"], url=s["url"], observed=s["observed_on"], match=s["match_confidence"])
        else:
            f("G", "current_raise", {"amount": s["value"], "currency": "EUR", "stage": None, "open": True}, s["source_name"],
              evidence=_j(s["details"]).get("text") or s["title"], url=s["url"], match=s["match_confidence"])
    if (st["stage"] or "unknown") != "unknown":
        f("G", "stage", ROUND_STAGE.get(st["stage"], "other"), "seed", evidence=f"Curated stage: {st['stage']}")
    for r in c.execute("""SELECT si.*, i.name FROM startup_investors si JOIN investors i ON i.id=si.investor_id WHERE si.startup_id=?""", (sid,)):
        f("Api", "investor", {"name": r["name"], "role": r["role"], "rounds": r["rounds"], "first_seen": r["first_seen"]}, "funding_rounds",
          related=investors.get(r["investor_id"]), observed=r["first_seen"], evidence=f"{r['name']} ({r['role']})")

    # J. signals for monitoring ---------------------------------------------------------------------------------
    for s in c.execute("SELECT * FROM startup_signals WHERE startup_id=? AND signal_type IN ('news','launch')", (sid,)):
        f("J", "news", {"date": s["observed_on"], "headline": s["title"], "url": s["url"], "type": news_type(s["title"])}, s["source_name"],
          evidence=s["title"], url=s["url"], observed=s["observed_on"], match=s["match_confidence"])

    # X. StartupGo extensions -----------------------------------------------------------------------------------
    for s in c.execute("""SELECT * FROM startup_signals WHERE startup_id=? AND
                          (signal_type IN ('job','repo','web_history','website') OR (signal_type='registry' AND unit IN ('insolvency','psc')))""", (sid,)):
        field = {"job": "open_role", "repo": "repo", "web_history": "web_history", "website": "website_text"}.get(s["signal_type"]) \
            or ("insolvency_case" if s["unit"] == "insolvency" else "beneficial_owner")
        f("Api", field, {"title": s["title"], "value": s["value"], "unit": s["unit"], **_j(s["details"])}, s["source_name"],
          evidence=s["title"], url=s["url"], observed=s["observed_on"], match=s["match_confidence"])
    for r in c.execute("SELECT * FROM sources WHERE startup_id=?", (sid,)):
        f("Api", "reference", {"title": r["title"]}, "seed", url=r["url"], evidence=r["title"], status="claimed")
    for n in c.execute("SELECT * FROM notes WHERE startup_id=?", (sid,)):
        f("Api", "analyst_note", {"author": n["author"], "body": n["body"], "created_at": n["created_at"]}, "analyst",
          evidence=n["body"], observed=n["created_at"], status="claimed")


def priced_rounds(events: list) -> list[dict]:
    """UK priced allotments grouped into rounds: same price within 2%, gaps under 180 days, at least 100k raised (as features.py)."""
    groups: list[dict] = []
    for e in events:
        d = datetime.strptime(e["event_date"][:10], "%Y-%m-%d").date()
        g = next((g for g in reversed(groups) if abs(e["price_per_share"] / g["price"] - 1) <= 0.02 and (d - g["end"]).days <= 180), None)
        if g:
            g["end"], g["amount"], g["n"] = d, g["amount"] + (e["amount"] or 0), g["n"] + 1
        else:
            groups.append({"start_d": d, "end": d, "price": e["price_per_share"], "amount": e["amount"] or 0, "currency": e["currency"],
                           "n": 1, "url": e["source_url"]})
    return [{**g, "start": g["start_d"].isoformat()} for g in groups if g["amount"] >= 100_000]


def _candidates(b: Builder) -> None:
    for p in b.conn.execute("SELECT * FROM blueinvest_profiles WHERE startup_id IS NULL").fetchall():
        key = f"blueinvest:{p['other_id']}"
        if b.conn.execute("SELECT 1 FROM entities WHERE key=? AND kind='startup'", (key,)).fetchone():
            b.seen.add(key)  # the Agent made this lead a startup (its entry was accepted): keep it one
            continue
        eid = b.entity(key, "candidate", p["company"] or p["name"], website=p["website"],
                       domain=domain(p["website"]) if p["website"] else None, country=p["country"], sector=p["sector"],
                       blue_sector=BLUE_SECTOR.get((p["sector"] or "").lower(), "other"), tagline=p["name"][:200],
                       description=p["summary"], blueinvest_id=str(p["other_id"]), pipeline_stage="candidate")
        if p["trl"]:
            b.fact(eid, "C", "dev_stage", TRL_TO_DEV_STAGE[p["trl"]], "blueinvest_profile", url=p["url"], evidence=p["trl_text"] or f"TRL {p['trl']}")
        if p["funding_sought_eur"]:
            b.fact(eid, "G", "current_raise", {"amount": p["funding_sought_eur"], "currency": "EUR", "stage": None, "open": True},
                   "blueinvest_profile", url=p["url"], evidence=(p["financial_needs"] or "")[:500], match="medium")


def _funding_calls(b: Builder) -> None:
    for o in b.conn.execute("SELECT * FROM funding_opportunities").fetchall():
        eid = b.entity(f"call:{o['source_name']}:{o['external_ref']}", "funding_call", o["title"][:300], website=o["url"])
        b.fact(eid, "Api", "call", {"kind": o["kind"], "status": o["status"], "opens_on": o["opens_on"], "deadline": o["deadline"],
                                  "amount": o["amount"], "currency": o["currency"], "organisation": o["organisation"], "ref": o["external_ref"]},
               o["source_name"], url=o["url"], evidence=o["title"], observed=o["opens_on"])


def _assessments(b: Builder) -> None:
    c = b.conn
    kpis: dict[int, dict] = {}
    for k in c.execute("SELECT * FROM startup_ocean_kpis"):
        kpis.setdefault(k["startup_id"], {})[k["kpi_code"]] = {"level": k["evidence_level"], "claim": k["claim"], "source_url": k["source_url"]}
    for a in c.execute("SELECT * FROM readiness_assessments ORDER BY assessed_on, id").fetchall():
        engine = "seed-estimate" if "seed estimate" in (a["assessor"] or "").lower() else "analyst"
        c.execute("""INSERT OR REPLACE INTO assessments (entity_id, assessed_at, engine, assessor, confidence, trl, brl, crl, iprl, tmrl, frl,
                                                         navigator_kpis, rationale) VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?)""",
                  (a["startup_id"], a["assessed_on"], engine, a["assessor"], a["confidence"], a["trl"], a["brl"], a["crl"], a["iprl"],
                   a["tmrl"], a["frl"], json.dumps(kpis.get(a["startup_id"], {})), a["rationale"]))
    as_of = c.execute("SELECT MAX(as_of) FROM startup_features").fetchone()[0]
    if not as_of:
        return
    for (sid,) in c.execute("SELECT DISTINCT startup_id FROM startup_features WHERE as_of=?", (as_of,)).fetchall():
        feats = {r["feature"]: {"value": r["value_num"], "text": r["value_text"], "evidence": _j(r["evidence"]) if r["evidence"] else None}
                 for r in c.execute("SELECT * FROM startup_features WHERE startup_id=? AND as_of=?", (sid, as_of))}
        v = lambda n: (feats.get(n) or {}).get("value")  # noqa: E731
        t = lambda n: (feats.get(n) or {}).get("text")  # noqa: E731
        flags = [name for name, hit in (("distress", v("distress_flag") == 1),
                                         ("registry status not active", t("registry_status") not in (None, "active")),
                                         ("down round", v("down_round_flag") == 1), ("no round in 24 months", v("no_round_24m") == 1),
                                         ("founder departures", v("founder_retention") is not None and v("founder_retention") < 0.5),
                                         ("TRL self-report far from estimate", v("trl_gap") is not None and abs(v("trl_gap")) >= 2)) if hit]
        gaps = [{"code": f"{r['section_code']}{r['item_no']}", "name": r["name"], "priority": r["priority"]}
                for r in c.execute("""SELECT p.* FROM startup_parameter_status s JOIN assessment_parameters p ON p.id=s.parameter_id
                                      WHERE s.startup_id=? AND s.status='empty' ORDER BY p.priority, p.section_code, p.item_no""", (sid,))]
        peers = [{"name": r["name"], "similarity": r["similarity"], "trl": r["trl"], "sector": r["sector"], "source": "blueinvest"}
                 for r in c.execute("SELECT * FROM startup_external_peers WHERE startup_id=? ORDER BY similarity DESC LIMIT 5", (sid,))]
        peers += [{"name": r["name"], "similarity": r["similarity"], "source": "startupgo"}
                  for r in c.execute("""SELECT s.name, p.similarity FROM startup_peers p JOIN startups s ON s.id=p.peer_id WHERE p.startup_id=?
                                        ORDER BY p.similarity DESC LIMIT 3""", (sid,))]
        c.execute("""INSERT OR REPLACE INTO assessments (entity_id, assessed_at, engine, assessor, red_flags, data_gaps, peers, features)
                     VALUES (?,?, 'startupgo-pipeline', 'Modules/DataAPIs/features.py', ?,?,?,?)""",
                  (sid, as_of, json.dumps(flags), json.dumps(gaps), json.dumps(peers), json.dumps(feats, default=str)))


# ---------------------------------------------------------------------------------------------------------------
# Views named like main's tables, over the 3 tables (read compatibility for Backend/ and Modules/Search)
# ---------------------------------------------------------------------------------------------------------------
LEVELS = "crl IS NOT NULL AND trl IS NOT NULL AND brl IS NOT NULL AND iprl IS NOT NULL AND tmrl IS NOT NULL AND frl IS NOT NULL"
COMPAT_VIEWS = {
    # Only startups with a full readiness assessment: main's list endpoint needs one to score them.
    "startups": f"""SELECT e.id, e.slug, e.name, e.tagline, e.description, e.sector, e.country, e.city, e.founded_year, e.website,
                           e.stage, e.pipeline_stage, e.created_at, e.updated_at
                    FROM entities e WHERE e.kind='startup' AND EXISTS (SELECT 1 FROM assessments a WHERE a.entity_id=e.id AND {LEVELS})""",
    "readiness_assessments": f"""SELECT id, entity_id AS startup_id, assessed_at AS assessed_on, COALESCE(assessor, engine) AS assessor,
                                        COALESCE(confidence, 'low') AS confidence, crl, trl, brl, iprl, tmrl, frl, rationale
                                 FROM assessments WHERE {LEVELS}""",
    "startup_ocean_kpis": """SELECT entity_id AS startup_id, json_extract(value,'$.kpi') AS kpi_code, json_extract(value,'$.level') AS evidence_level,
                                    json_extract(value,'$.claim') AS claim, source_url FROM facts WHERE field='navigator_kpi' AND is_current=1""",
    # Rounds from the funding_rounds table, analysts (Backend) and the Agent: their values carry these keys.
    "funding_rounds": """SELECT id, entity_id AS startup_id, json_extract(value,'$.round_type') AS round_type, json_extract(value,'$.amount') AS amount,
                                json_extract(value,'$.currency') AS currency, json_extract(value,'$.announced_on') AS announced_on,
                                json_extract(value,'$.lead_investors') AS lead_investors, json_extract(value,'$.notes') AS notes, source_url
                         FROM facts WHERE source_name IN ('funding_rounds','analyst','agent') AND field IN ('equity_rounds','grants') AND is_current=1""",
    "sources": """SELECT id, entity_id AS startup_id, json_extract(value,'$.title') AS title, source_url AS url FROM facts WHERE field='reference'""",
    "notes": """SELECT id, entity_id AS startup_id, json_extract(value,'$.author') AS author, json_extract(value,'$.body') AS body,
                       json_extract(value,'$.created_at') AS created_at FROM facts WHERE field='analyst_note'""",
}
REFERENCE_TABLES = ("readiness_dimensions", "readiness_levels", "ocean_impact_areas", "ocean_kpis",
                    "feature_definitions")  # frameworks and the feature catalogue, stored as VALUES views
SCHEMA_SQL = Path(__file__).resolve().parents[2] / "DB" / "schema.sql"


def compat_sql(conn: sqlite3.Connection) -> list[str]:
    """CREATE VIEW statements: main's data tables over the 3 tables, framework tables as literal VALUES."""
    stmts = [f"CREATE VIEW {name} AS {sql}" for name, sql in COMPAT_VIEWS.items()]
    for t in REFERENCE_TABLES:
        cols = [r[1] for r in conn.execute(f"PRAGMA table_info({t})")]
        rows = conn.execute(f"SELECT {', '.join(cols)} FROM {t}").fetchall()
        lit = lambda x: "NULL" if x is None else str(x) if isinstance(x, (int, float)) else "'" + str(x).replace("'", "''") + "'"  # noqa: E731
        values = ", ".join("(" + ", ".join(lit(x) for x in r) + ")" for r in rows)
        body = f"VALUES {values}" if rows else f"SELECT {', '.join(['NULL'] * len(cols))} WHERE 0"  # an empty table: an empty view
        stmts.append(f"CREATE VIEW {t}({', '.join(cols)}) AS {body}")
    return stmts


def unified_sql(conn: sqlite3.Connection) -> str:
    """The 3-table copy's schema as a script: the tables from schema.sql, then the views (dropped and created again)."""
    schema = SCHEMA_SQL.read_text(encoding="utf-8")
    tables = schema[schema.index("-- One row per real-world thing."):].strip()
    views = [f"DROP VIEW IF EXISTS {name};\n{stmt};" for name, stmt in
             zip([*COMPAT_VIEWS, *REFERENCE_TABLES], compat_sql(conn))]
    header = ("-- StartupGo's database: 3 tables (entities, facts, assessments) and read-only views named like the older tables.\n"
              "-- Generated by Modules/DataAPIs/unify.py --sql from DB/schema.sql and the runtime DB's reference tables; do not edit.\n"
              "-- Writers (Backend, Agent) write the 3 tables; the views are for reading.")
    return "\n\n".join([header, tables, *views]) + "\n"


def preview(src: Path, dst: Path) -> Path:
    """Write a copy of ``src`` that keeps only entities/facts/assessments and adds the compatibility views."""
    dst.parent.mkdir(parents=True, exist_ok=True)
    dst.unlink(missing_ok=True)
    s = sqlite3.connect(src)
    stmts = compat_sql(s)
    s.execute("VACUUM INTO ?", (str(dst),))
    s.close()
    d = sqlite3.connect(dst)
    d.execute("PRAGMA foreign_keys = OFF")
    for (name, kind) in d.execute("SELECT name, type FROM sqlite_master WHERE type IN ('view','table') AND name NOT LIKE 'sqlite_%'").fetchall():
        if name not in ("entities", "facts", "assessments"):
            d.execute(f"DROP {kind.upper()} IF EXISTS {name}")
    for stmt in stmts:
        d.execute(stmt)
    d.commit()
    d.execute("VACUUM")
    d.close()
    return dst


def main(argv=None) -> int:
    p = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    p.add_argument("--preview", type=Path, help="also write a 3-table-only copy with compatibility views here")
    p.add_argument("--sql", type=Path, help="also write the 3-table copy's schema (tables + views) as SQL here")
    a = p.parse_args(argv)
    conn = ingest.open_db()
    counts = build(conn)
    print("unified:", ", ".join(f"{k} {v}" for k, v in counts.items()))
    if a.preview:
        print(f"preview written: {preview(ingest.db_path(), a.preview)}")
    if a.sql:
        a.sql.write_text(unified_sql(conn), encoding="utf-8")
        print(f"schema written: {a.sql}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
