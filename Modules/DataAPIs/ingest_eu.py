#!/usr/bin/env python3
"""Load EU and ocean-specific sources: CORDIS grants, ocean patent classes, BlueInvest pipeline, FR/NO registers.

  python3 ingest_eu.py                       all steps for every startup in the DB
  python3 ingest_eu.py --blueinvest-refresh  re-crawl the BlueInvest pipeline list (36 pages, ~1 request/s)
  python3 ingest_eu.py --only cordis,patents  run selected steps: cordis, patents, blueinvest, registers

All sources are free and keyless. Matching to our startups is strict (legal-name tokens, website domain)
because names like "Sofar" or "Oceanium" also match unrelated projects.
"""
from __future__ import annotations

import html as htmllib
import json
import re
import sys
import time
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent))
import ingest  # noqa: E402  (registers all scrapers, loads .env)
from ingest import domain, ext_id, fetch, norm, signal, suggest  # noqa: E402

LEGAL_FORMS = {"spf", "ltd", "limited", "bv", "lda", "sa", "sas", "sarl", "gmbh", "as", "asa", "aps", "oy", "ab", "sl", "srl", "inc",
               "plc", "nv", "ehf", "hf", "ug", "spa", "llc", "co", "company", "unipessoal", "holding", "group"}


def name_tokens(s: str) -> list[str]:
    return [t for t in re.findall(r"[a-z0-9]+", (s or "").lower()) if t not in LEGAL_FORMS]


def same_company(startup_name: str, legal_name: str) -> bool:
    """Legal name must start with the startup's name tokens: 'SPF OCEAN RAINFOREST' ok, 'NOTPLASTIC LTD' not Notpla."""
    want, got = name_tokens(startup_name), name_tokens(legal_name)
    return bool(want) and got[: len(want)] == want


def as_list(x):
    return x if isinstance(x, list) else ([] if x is None else [x])


def fnum(x):
    try:
        return float(x)
    except (TypeError, ValueError):
        return None


# ---------------------------------------------------------------------------
# CORDIS
# ---------------------------------------------------------------------------
def ingest_cordis(conn, st):
    sid, name = st["id"], st["name"]
    conn.execute("DELETE FROM eu_grants WHERE startup_id=?", (sid,))
    query = f"contenttype='project' AND '{name}'"
    page, seen = 1, 0
    while page <= 5:
        d, f = fetch(conn, "cordis_projects", sid, query=query, num=50, p=page)
        hits = as_list(((d or {}).get("hits") or {}).get("hit"))
        total = int(((d or {}).get("result") or {}).get("header", {}).get("totalHits") or 0)
        for h in hits:
            p = h.get("project") or {}
            assoc = (p.get("relations") or {}).get("associations") or {}
            orgs = as_list(assoc.get("organization"))
            progs = as_list(assoc.get("programme"))
            topics = [x.get("code") for x in progs if (x.get("@attributes") or {}).get("type") == "relatedTopic"]
            bases = [x.get("code") for x in progs if (x.get("@attributes") or {}).get("type") == "relatedLegalBasis"]
            codes = " ".join(topics + bases)
            framework = "H2020" if "H2020" in codes else "HORIZON" if "HORIZON" in codes else "FP7" if "FP7" in codes else None
            is_eic = int(bool(re.search(r"EIC|SMEInst|H2020-EU\.2\.3\.1|HORIZON\.3\.1", codes)))
            is_mission = int(bool(re.search(r"MISS.*OCEAN|OCEAN.*MISS", codes)))
            cats = [c.get("title") for c in as_list((p.get("relations") or {}).get("categories", {}).get("category"))
                    if (c.get("@attributes") or {}).get("classification") == "euroSciVoc"]
            for o in orgs:
                if not same_company(name, o.get("legalName", "")):
                    continue
                a = o.get("@attributes") or {}
                conn.execute("""INSERT OR REPLACE INTO eu_grants
                    (startup_id, project_id, acronym, title, framework, topic_codes, legal_basis, role, ec_contribution, total_cost,
                     project_ec_max, sme, org_legal_name, org_vat, org_country, partners, start_date, end_date, status, is_eic,
                     is_mission_ocean, categories, url) VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)""",
                             (sid, p.get("id"), p.get("acronym"), p.get("title"), framework, json.dumps(topics), json.dumps(bases),
                              a.get("type") or "participant", fnum(a.get("ecContribution")), fnum(a.get("totalCost")), fnum(p.get("ecMaxContribution")),
                              int(a.get("sme") == "true") if a.get("sme") else None, o.get("legalName"), o.get("vatNumber"),
                              (o.get("address") or {}).get("country"), max(len(orgs) - 1, 0), p.get("startDate"), p.get("endDate"),
                              p.get("status"), is_eic, is_mission, json.dumps(cats),
                              f"https://cordis.europa.eu/project/id/{p.get('id')}"))
                ext_id(conn, sid, "cordis_org", o.get("id"), "cordis_projects", None,
                       {"legal_name": o.get("legalName"), "vat": o.get("vatNumber"), "country": (o.get("address") or {}).get("country"),
                        "geolocation": (o.get("address") or {}).get("geolocation"), "sme": a.get("sme")}, "high", f)
        seen += len(hits)
        if not hits or seen >= total:
            break
        page += 1
    conn.commit()


# ---------------------------------------------------------------------------
# Patent classes (CPC) for patents we already hold
# ---------------------------------------------------------------------------
OCEAN_CPC = {  # prefix -> group. Class-based tagging misses patents whose *use* is marine (e.g. ship CO2 capture is B01D53).
    "A01K61": "aquaculture", "A01K63": "aquaculture", "A01K80": "aquaculture",
    "A01G33": "seaweed", "A23L17/60": "seaweed",
    # algae-derived products (extracts, alginates, algae in cosmetics/biocides)
    "C12N1/12": "marine-bio", "A61K36/02": "marine-bio", "A61K36/03": "marine-bio", "A61K36/04": "marine-bio", "A61K36/05": "marine-bio",
    "A61K8/9706": "marine-bio", "A01N65/03": "marine-bio", "C08L5/04": "marine-bio", "C08B37/0084": "marine-bio",
    "Y02E10/3": "ocean-energy", "F03B13/12": "ocean-energy", "F03B13/14": "ocean-energy", "F03B13/16": "ocean-energy",
    "F03B13/18": "ocean-energy", "F03B13/20": "ocean-energy", "F03B13/22": "ocean-energy", "F03B13/24": "ocean-energy",
    "F03B13/26": "ocean-energy", "Y02E10/727": "ocean-energy",
    "B63": "vessels", "Y02T70": "ship-emissions", "E02B15": "marine-cleanup",
    "G01S15": "ocean-sensing", "G01C13": "ocean-sensing", "G01V1/38": "ocean-sensing", "G01N33/18": "ocean-sensing",
}


def ocean_group(code: str) -> str | None:
    c = code.replace(" ", "")
    for prefix, group in sorted(OCEAN_CPC.items(), key=lambda kv: -len(kv[0])):
        if c.startswith(prefix):
            return group
    return None


def retag_patent_classes(conn):
    """Re-apply OCEAN_CPC to stored codes (no refetch) and refresh each patent signal's ocean_groups."""
    for r in conn.execute("SELECT rowid, cpc_code FROM patent_classes").fetchall():
        conn.execute("UPDATE patent_classes SET ocean_group=? WHERE rowid=?", (ocean_group(r["cpc_code"]), r["rowid"]))
    for sig in conn.execute("SELECT id, startup_id, title, details FROM startup_signals WHERE signal_type='patent'").fetchall():
        number = sig["title"].split(":")[0].strip()
        groups = sorted({g for (g,) in conn.execute("SELECT DISTINCT ocean_group FROM patent_classes WHERE startup_id=? AND publication_number=? "
                                                     "AND ocean_group IS NOT NULL", (sig["startup_id"], number))})
        det = json.loads(sig["details"] or "{}")
        det["ocean_groups"] = groups
        conn.execute("UPDATE startup_signals SET details=? WHERE id=?", (json.dumps(det), sig["id"]))
    conn.commit()


def ingest_patent_classes(conn, st):
    sid = st["id"]
    for sig in conn.execute("SELECT id, title, details FROM startup_signals WHERE startup_id=? AND signal_type='patent'", (sid,)).fetchall():
        number = sig["title"].split(":")[0].strip()
        page, f = fetch(conn, "google_patents_page", sid, number=number)
        if not isinstance(page, str) or "itemprop" not in page:
            continue
        codes = sorted(set(c.strip() for c in re.findall(r'itemprop="Code">([A-Z][0-9A-Z/ ]+)<', page) if "/" in c))
        status = next((s.strip() for s in re.findall(r'itemprop="(?:legalStatusIfi|ifiStatus)"[^>]*>([^<]+)<', page) if s.strip()), None)
        conn.execute("DELETE FROM patent_classes WHERE startup_id=? AND publication_number=?", (sid, number))
        for c in codes:
            conn.execute("INSERT OR IGNORE INTO patent_classes VALUES (?,?,?,?)", (sid, number, c, ocean_group(c)))
        det = json.loads(sig["details"] or "{}")
        det.update({"legal_status": status, "cpc_count": len(codes), "ocean_groups": sorted({g for g in map(ocean_group, codes) if g})})
        conn.execute("UPDATE startup_signals SET details=? WHERE id=?", (json.dumps(det), sig["id"]))
        time.sleep(0.5)
    conn.commit()


# ---------------------------------------------------------------------------
# BlueInvest pipeline
# ---------------------------------------------------------------------------
def _text(fragment: str) -> str:
    return re.sub(r"\s+", " ", htmllib.unescape(re.sub(r"<[^>]+>", " ", fragment))).strip()


def parse_pipeline_page(page: str) -> tuple[list[dict], int]:
    out = []
    for card in page.split('class="row stripe"')[1:]:
        m = re.search(r'other_id%5D=(\d+)">([^<]+)</a></h4>', card)
        if not m:
            continue
        sub = re.search(r'class="subtext">(.*?)</div>', card, re.S)
        trl = re.search(r"Project TRL:\s*(TRL\s*(\d)[^<]*)", card)
        sector = re.search(r"Main sector:\s*([^<]+)<", card)
        out.append({"other_id": int(m.group(1)), "name": _text(m.group(2)), "summary": _text(sub.group(1))[:2000] if sub else None,
                    "trl": int(trl.group(2)) if trl else None, "trl_text": _text(trl.group(1)) if trl else None,
                    "sector": _text(sector.group(1)) if sector else None})
    pages = [int(x) for x in re.findall(r"params\[page\]=(\d+)", page)]
    return out, max(pages or [1])


AMOUNT = re.compile(r"(?:(?:€|EUR)\s*(?P<a>\d[\d.,\s]*\d|\d)\s*(?P<ua>k|m|mn|million|millions|bn|billion)?\b)|"
                    r"(?:(?P<b>\d[\d.,\s]*\d|\d)\s*(?P<ub>k|m|mn|million|millions|bn|billion)?\s*(?:€|EUR|euros?)\b)", re.I)
MULT = {"k": 1e3, "m": 1e6, "mn": 1e6, "million": 1e6, "millions": 1e6, "bn": 1e9, "billion": 1e9}


def largest_eur(text: str) -> float | None:
    vals = []
    for m in AMOUNT.finditer(text or ""):
        num, unit = (m.group("a"), m.group("ua")) if m.group("a") else (m.group("b"), m.group("ub"))
        s = num.replace(" ", "").replace(" ", "")
        if unit:
            s = s.replace(",", ".")
            s = s.replace(".", "", s.count(".") - 1) if s.count(".") > 1 else s
        elif re.fullmatch(r"\d{1,3}([.,]\d{3})+", s):
            s = re.sub(r"[.,]", "", s)
        else:
            s = s.replace(",", ".")
        try:
            v = float(s) * MULT.get((unit or "").lower(), 1)
        except ValueError:
            continue
        if v >= 1000:
            vals.append(v)
    return max(vals) if vals else None


def parse_profile(page: str) -> dict:
    lines = [ln.strip() for ln in htmllib.unescape(re.sub(r"<[^>]+>", "\n", page)).split("\n") if ln.strip()]
    get = lambda label: lines[lines.index(label) + 1] if label in lines and lines.index(label) + 1 < len(lines) else None  # noqa: E731
    out = {"trl_text": get("TRL")}
    if "Company behind project" in lines:
        i = lines.index("Company behind project")
        out.update(company=lines[i + 1], country=lines[i + 2], sector=lines[i - 1])
    if "Financial Needs" in lines:
        i = lines.index("Financial Needs")
        j = lines.index("Planned Funding Allocation") if "Planned Funding Allocation" in lines else i + 6
        out["financial_needs"] = " ".join(lines[i + 1:j])[:3000]
        out["funding_sought_eur"] = largest_eur(out["financial_needs"])
    back = lines.index("Back to Pipeline") if "Back to Pipeline" in lines else len(lines)
    sites = [ln for ln in lines[:back] if re.match(r"https?://", ln) and "converve" not in ln]
    out["website"] = sites[-1] if sites else None
    return out


def crawl_blueinvest(conn, refresh=False):
    have = conn.execute("SELECT COUNT(*) FROM blueinvest_profiles").fetchone()[0]
    if have and not refresh:
        return have
    page_no, last = 1, 1
    while page_no <= last:
        page, _ = fetch(conn, "blueinvest_pipeline", None, page=page_no)
        if not isinstance(page, str):
            break
        cards, last = parse_pipeline_page(page)
        for c in cards:
            url = f"{ingest.SRC['blueinvest_profile'].endpoint}&params%5Bevent_id%5D=1&params%5Bshow%5D=comp&params%5Bother_id%5D={c['other_id']}"
            conn.execute("""INSERT INTO blueinvest_profiles (other_id, name, summary, trl, trl_text, sector, url) VALUES (?,?,?,?,?,?,?)
                            ON CONFLICT(other_id) DO UPDATE SET name=excluded.name, summary=excluded.summary, trl=excluded.trl,
                              trl_text=excluded.trl_text, sector=excluded.sector, fetched_at=datetime('now')""",
                         (c["other_id"], c["name"], c["summary"], c["trl"], c["trl_text"], c["sector"], url.replace("pipeline_front.html?action=detail&", "pipeline_front.html?action=detail&")))
        conn.commit()
        page_no += 1
        time.sleep(1)
    return conn.execute("SELECT COUNT(*) FROM blueinvest_profiles").fetchone()[0]


def match_blueinvest(conn, st):
    sid, n = st["id"], norm(st["name"])
    sites = {domain(st["website"])} | {domain(r[0]) for r in conn.execute(
        "SELECT value FROM field_suggestions WHERE startup_id=? AND field='website' AND status!='rejected'", (sid,))}
    sites.discard(None)
    known = {int(r[0]) for r in conn.execute(  # the profile a startup was imported from (discover.py) is always a candidate:
        "SELECT external_id FROM startup_external_ids WHERE startup_id=? AND id_type='blueinvest_profile'", (sid,))}  # profiles are often named after a product
    conn.execute("UPDATE blueinvest_profiles SET startup_id=NULL WHERE startup_id=?", (sid,))
    cands = [r for r in conn.execute("SELECT other_id, name FROM blueinvest_profiles").fetchall()
             if r["other_id"] in known or norm(r["name"])[:6] == n[:6] or n in norm(r["name"])]
    cands.sort(key=lambda r: r["other_id"] not in known)  # known profile first, so the 6-candidate cap never drops it
    for c in cands[:6]:
        page, f = fetch(conn, "blueinvest_profile", sid, other_id=c["other_id"])
        if not isinstance(page, str):
            continue
        d = parse_profile(page)
        by_site = bool(d.get("website") and domain(d["website"]) in sites)
        by_name = same_company(st["name"], d.get("company") or "") or same_company(st["name"], c["name"])
        if not (by_site or by_name):
            continue
        conn.execute("""UPDATE blueinvest_profiles SET company=?, country=?, financial_needs=?, funding_sought_eur=?, website=?, startup_id=?,
                          trl_text=COALESCE(?, trl_text), sector=COALESCE(sector, ?) WHERE other_id=?""",
                     (d.get("company"), d.get("country"), d.get("financial_needs"), d.get("funding_sought_eur"), d.get("website"), sid,
                      d.get("trl_text"), d.get("sector"), c["other_id"]))
        row = conn.execute("SELECT * FROM blueinvest_profiles WHERE other_id=?", (c["other_id"],)).fetchone()
        conf = "high" if by_site else "medium"
        ext_id(conn, sid, "blueinvest_profile", c["other_id"], "blueinvest_profile", row["url"],
               {"name": row["name"], "company": row["company"], "country": row["country"], "sector": row["sector"]}, conf, f)
        if row["trl"]:
            signal(conn, sid, "blueinvest_profile", "profile", f"BlueInvest TRL {row['trl']}: {row['name']}", row["url"], None,
                   row["trl"], "trl", {"trl_text": row["trl_text"], "sector": row["sector"]}, conf, f)
        if row["funding_sought_eur"]:
            signal(conn, sid, "blueinvest_profile", "profile", f"BlueInvest funding sought: EUR {row['funding_sought_eur']:,.0f}", row["url"], None,
                   row["funding_sought_eur"], "eur_sought", {"text": (row["financial_needs"] or "")[:600]}, "medium", f)
        if not st["website"] and row["website"]:
            site = re.sub(r"//ww\.", "//www.", row["website"], count=1)  # "ww." typo seen in BlueInvest profiles
            suggest(conn, st, "website", site, "blueinvest_profile", "BlueInvest profile website", conf, f)
    conn.commit()


# ---------------------------------------------------------------------------
# National registers (only for startups in that country)
# ---------------------------------------------------------------------------
FR_BANDS = {"00": (0, "0"), "01": (1.5, "1-2"), "02": (4, "3-5"), "03": (7.5, "6-9"), "11": (15, "10-19"), "12": (35, "20-49"),
            "21": (75, "50-99"), "22": (150, "100-199"), "31": (225, "200-249"), "32": (375, "250-499"), "41": (750, "500-999"),
            "42": (1500, "1000-1999"), "51": (3500, "2000-4999"), "52": (7500, "5000-9999"), "53": (10000, "10000+")}


def add_person(conn, sid, name, role, source, resigned=None):
    conn.execute("INSERT INTO people (name) SELECT ? WHERE NOT EXISTS (SELECT 1 FROM people WHERE name=? AND ch_officer_id IS NULL)", (name, name))
    pid = conn.execute("SELECT id FROM people WHERE name=? AND ch_officer_id IS NULL", (name,)).fetchone()[0]
    conn.execute("INSERT OR REPLACE INTO startup_people (startup_id, person_id, role, is_founder, resigned_on, source_name) VALUES (?,?,?,0,?,?)",
                 (sid, pid, role, resigned, source))


def ingest_fr(conn, st):
    sid = st["id"]
    d, f = fetch(conn, "fr_recherche_entreprises", sid, q=st["name"], per_page=10)
    for r in (d or {}).get("results", []):
        if not same_company(st["name"], r.get("nom_complet") or r.get("nom_raison_sociale") or ""):
            continue
        band = FR_BANDS.get(r.get("tranche_effectif_salarie") or "")
        fin = r.get("finances") or {}
        last_year = max(fin) if fin else None
        status = {"A": "active", "C": "closed"}.get(r.get("etat_administratif"), r.get("etat_administratif"))
        det = {"company_name": r.get("nom_complet"), "status": status, "date_of_creation": r.get("date_creation"),
               "closed_on": r.get("date_fermeture"), "legal_form_code": r.get("nature_juridique"), "naf": r.get("activite_principale"),
               "category": r.get("categorie_entreprise"), "headcount_band": band[1] if band else None,
               "address": (r.get("siege") or {}).get("adresse"), "finances": fin}
        url = f"https://annuaire-entreprises.data.gouv.fr/entreprise/{r['siren']}"
        ext_id(conn, sid, "siren", r["siren"], "fr_recherche_entreprises", url, det, "medium", f)
        signal(conn, sid, "fr_recherche_entreprises", "registry", f"French register: {det['company_name']} ({status})", url, r.get("date_creation"),
               details=det, conf="medium", fetch_id=f)
        if band:
            signal(conn, sid, "fr_recherche_entreprises", "profile", f"Employees (band): {band[1]}", url, r.get("annee_tranche_effectif_salarie"),
                   band[0], "employees", {"band": band[1]}, "medium", f)
        if last_year and (fin[last_year] or {}).get("ca"):  # 0 usually means accounts not disclosed: keep it unknown, not zero
            signal(conn, sid, "fr_recherche_entreprises", "profile", f"Revenue {last_year}: EUR {fin[last_year]['ca']:,.0f}", url, f"{last_year}-12-31",
                   fin[last_year]["ca"], "revenue_eur", {"net_result": fin[last_year].get("resultat_net")}, "medium", f)
        if r.get("date_creation"):
            suggest(conn, st, "founded_year", r["date_creation"][:4], "fr_recherche_entreprises", f"SIREN {r['siren']} date_creation", "medium", f)
        for p in r.get("dirigeants") or []:
            if p.get("type_dirigeant") == "personne physique":  # birth dates are in the payload; deliberately not stored
                add_person(conn, sid, f"{p.get('nom', '').strip()}, {p.get('prenoms', '').strip()}", p.get("qualite") or "dirigeant", "fr_recherche_entreprises")
        break
    conn.commit()


def ingest_no(conn, st):
    sid = st["id"]
    d, f = fetch(conn, "no_brreg", sid, navn=st["name"], size=20)
    for e in ((d or {}).get("_embedded") or {}).get("enheter", []):
        if not same_company(st["name"], e.get("navn", "")):
            continue
        orgnr = e["organisasjonsnummer"]
        status = ("bankrupt" if e.get("konkurs") else "liquidation" if (e.get("underAvvikling") or e.get("underTvangsavviklingEllerTvangsopplosning"))
                  else "active")
        det = {"company_name": e.get("navn"), "status": status, "date_of_creation": e.get("stiftelsesdato") or e.get("registreringsdatoEnhetsregisteret"),
               "legal_form": (e.get("organisasjonsform") or {}).get("kode"), "employees": e.get("antallAnsatte"),
               "nace": (e.get("naeringskode1") or {}).get("kode"), "nace_text": (e.get("naeringskode1") or {}).get("beskrivelse"),
               "address": ", ".join((e.get("forretningsadresse") or {}).get("adresse") or [])}
        url = f"https://virksomhet.brreg.no/nb/oppslag/enheter/{orgnr}"
        ext_id(conn, sid, "no_orgnr", orgnr, "no_brreg", url, det, "medium", f)
        signal(conn, sid, "no_brreg", "registry", f"Norwegian register: {det['company_name']} ({status})", url, det["date_of_creation"],
               details=det, conf="medium", fetch_id=f)
        if e.get("harRegistrertAntallAnsatte") and e.get("antallAnsatte") is not None:
            signal(conn, sid, "no_brreg", "profile", f"Employees: {e['antallAnsatte']}", url, None, e["antallAnsatte"], "employees", None, "medium", f)
        if det["date_of_creation"]:
            suggest(conn, st, "founded_year", det["date_of_creation"][:4], "no_brreg", f"orgnr {orgnr}", "medium", f)
        roles, _ = fetch(conn, "no_brreg", sid, orgnr=orgnr, roles=True)
        for g in (roles or {}).get("rollegrupper", []):
            for r in g.get("roller", []):
                person = (r.get("person") or {}).get("navn")
                if person:
                    add_person(conn, sid, f"{person.get('etternavn', '')}, {person.get('fornavn', '')} {person.get('mellomnavn', '') or ''}".strip(),
                               (r.get("type") or {}).get("beskrivelse") or "role", "no_brreg", "yes" if r.get("fratraadt") else None)
        break
    conn.commit()


def main(argv):
    only = set(next((a.split("=", 1)[1] for a in argv if a.startswith("--only=")), "cordis,patents,blueinvest,registers").split(","))
    conn = ingest.open_db()
    if "blueinvest" in only:
        print(f"-> BlueInvest pipeline: {crawl_blueinvest(conn, refresh='--blueinvest-refresh' in argv)} profiles")
    for st in conn.execute("SELECT * FROM startups ORDER BY id").fetchall():
        print(f"-> {st['name']}")
        if "cordis" in only:
            ingest_cordis(conn, st)
        if "patents" in only:
            ingest_patent_classes(conn, st)
        if "blueinvest" in only:
            match_blueinvest(conn, st)
        if "registers" in only:
            if st["country"] == "France":
                ingest_fr(conn, st)
            elif st["country"] == "Norway":
                ingest_no(conn, st)
    if "patents" in only or "retag" in only:
        retag_patent_classes(conn)
    q = lambda s: conn.execute(s).fetchone()[0]  # noqa: E731
    print(f"eu_grants {q('SELECT COUNT(*) FROM eu_grants')}, patent_classes {q('SELECT COUNT(*) FROM patent_classes')}, "
          f"blueinvest matched {q('SELECT COUNT(*) FROM blueinvest_profiles WHERE startup_id IS NOT NULL')}")


if __name__ == "__main__":
    main(sys.argv[1:])
