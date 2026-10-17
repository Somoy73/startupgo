#!/usr/bin/env python3
"""Build success-prediction features: round history, investor quality, serial founders, peers, risk.

Parameters follow Potanin et al. 2023 (arXiv:2309.15552) - rounds, investors, founders, categories -
plus the user's ranked list and ocean deep-tech additions. Every feature is point-in-time (as_of) and
carries the evidence it was computed from; a missing input means no row, never a zero.

  Backend/.venv/bin/python DataAPIs/features.py            fetch (UK SH01 + officers, SEC Form D) and compute
  Backend/.venv/bin/python DataAPIs/features.py --offline  recompute from what is already in the DB

Needs pypdf for SH01 PDFs (installed in Backend/.venv). Fetched PDFs are cached in DataAPIs/.cache/.
"""
from __future__ import annotations

import json
import math
import os
import re
import statistics
import subprocess
import sys
from datetime import date, datetime
from pathlib import Path

HERE = Path(__file__).parent
sys.path.insert(0, str(HERE))
import ingest  # noqa: E402  (also loads the scraper registry and .env)
from ingest import fetch, norm, now  # noqa: E402

CACHE = HERE / ".cache" / "sh01"
FX_TO_USD = {"USD": 1.0, "EUR": 1.08, "GBP": 1.27, "NOK": 0.093, "DKK": 0.145}  # same as Backend/app/scoring.py
TODAY = date.today()
AS_OF = TODAY.isoformat()


def usd(amount, currency):
    if amount is None or not currency:
        return None
    r = FX_TO_USD.get(currency.upper())
    return None if r is None else amount * r


def parse_date(s) -> date | None:
    """Accepts YYYY, YYYY-MM, YYYY-MM-DD; partial dates resolve to the first day of the period."""
    if not s:
        return None
    s = str(s)[:10]
    for fmt, pad in (("%Y-%m-%d", ""), ("%Y-%m", "-01"), ("%Y", "-01-01")):
        try:
            return datetime.strptime(s + pad, "%Y-%m-%d").date() if pad else datetime.strptime(s, fmt).date()
        except ValueError:
            continue
    return None


def months_between(a: date, b: date) -> float:
    return (b - a).days / 30.44


# ---------------------------------------------------------------------------
# Feature catalogue
# ---------------------------------------------------------------------------
FEATURES = [
    # name, group, description, unit, importance, origin, sources
    ("total_raised_usd", "rounds", "Total capital raised; largest of announced rounds, filings (Form D, priced SH01) and the PDL aggregate. All candidates kept in evidence.", "USD", "high", "paper", "funding_rounds, sec_form_d, uk_sh01, people_data_labs"),
    ("round_count", "rounds", "Number of distinct funding rounds (allotments within 90 days merged).", "rounds", "high", "paper", "funding_rounds, uk_sh01, sec_form_d, people_data_labs"),
    ("last_round_date", "rounds", "Date of the most recent round from any source.", "date", "high", "user-list", "all funding sources"),
    ("last_round_type", "rounds", "Stage of the most recent announced round.", None, "high", "paper", "funding_rounds, people_data_labs"),
    ("months_since_last_round", "rounds", "Months from the last round to the as-of date.", "months", "high", "user-list", "derived"),
    ("no_round_24m", "rounds", "1 if no round in the last 730 days: the paper's 'longtime' failure rule.", "flag", "high", "paper", "derived"),
    ("median_months_between_rounds", "rounds", "Median gap between consecutive rounds (funding speed).", "months", "high", "user-list", "derived"),
    ("funding_velocity_usd_per_year", "rounds", "Total raised divided by company age.", "USD/yr", "medium", "recommended", "derived"),
    ("latest_price_per_share", "rounds", "Price paid per share in the latest priced allotment (UK SH01).", "currency/share", "medium", "user-list", "uk_sh01"),
    ("implied_post_money", "rounds", "Latest priced allotment price x total shares after it (UK SH01).", "currency", "high", "user-list", "uk_sh01"),
    ("valuation_step_up", "rounds", "Latest priced share price / previous priced round's price.", "x", "high", "recommended", "uk_sh01"),
    ("down_round_flag", "rounds", "1 if any priced round was below the previous round's price (UK SH01).", "flag", "high", "recommended", "uk_sh01"),
    ("founder_other_ventures", "founders", "All other companies the founders direct or directed, any date (side projects, spin-outs, next venture).", "companies", "low", "recommended", "uk_companies_house_officer"),
    ("eu_grants_total_eur", "grants", "EU research/innovation funding received (sum of the company's own EU contribution, CORDIS).", "EUR", "high", "recommended", "cordis_projects"),
    ("eu_projects_count", "grants", "EU-funded projects the company takes part in (any role).", "projects", "medium", "recommended", "cordis_projects"),
    ("eu_projects_funded", "grants", "Of those, projects where the company itself receives EU money.", "projects", "medium", "recommended", "cordis_projects"),
    ("eu_coordinator_count", "grants", "EU projects the company coordinates (leadership signal).", "projects", "high", "recommended", "cordis_projects"),
    ("eu_first_grant_year", "grants", "Start year of the company's first EU project.", "year", "low", "recommended", "cordis_projects"),
    ("eu_active_projects", "grants", "EU projects currently running (signed, end date in the future).", "projects", "medium", "recommended", "cordis_projects"),
    ("eic_or_sme_instrument", "grants", "1 if funded by the EIC or the H2020 SME Instrument: highly selective startup programmes.", "flag", "high", "recommended", "cordis_projects"),
    ("mission_ocean_grant", "grants", "1 if part of the EU Mission 'Restore our Ocean and Waters'.", "flag", "medium", "recommended", "cordis_projects"),
    ("eu_consortium_links", "grants", "Total consortium partners across the company's EU projects (network reach; partners in several projects count each time).", "links", "medium", "recommended", "cordis_projects"),
    ("cordis_sme_confirmed", "grants", "1 if CORDIS records the company as an SME.", "flag", "low", "recommended", "cordis_projects"),
    ("grant_to_equity_ratio", "grants", "EU grants / total raised: grant dependency, typical for ocean deep tech.", "ratio", "medium", "recommended", "derived"),
    ("ocean_patent_count", "ocean", "Patents with at least one ocean-technology CPC class (aquaculture, seaweed, algae products, ocean energy, vessels, ship emissions, cleanup, ocean sensing).", "patents", "medium", "recommended", "google_patents_page"),
    ("ocean_patent_share", "ocean", "Ocean-class patents / patents with known classes. Misses marine-use patents filed in generic classes.", "0-1", "low", "recommended", "google_patents_page"),
    ("ocean_tech_groups", "ocean", "Ocean technology groups found in the company's patent classes.", "JSON", "low", "recommended", "google_patents_page"),
    ("blueinvest_listed", "ocean", "1 if the company is in the EU BlueInvest Project Pipeline (investor-facing showcase); 0 if not found.", "flag", "medium", "recommended", "blueinvest_pipeline"),
    ("blueinvest_trl", "ocean", "Self-reported TRL on the BlueInvest profile.", "1-9", "high", "recommended", "blueinvest_profile"),
    ("blueinvest_funding_sought_eur", "ocean", "Funding sought according to the BlueInvest profile (largest EUR amount in its financial needs text).", "EUR", "medium", "recommended", "blueinvest_profile"),
    ("blueinvest_sector", "ocean", "BlueInvest blue-economy sector.", None, "medium", "recommended", "blueinvest_profile"),
    ("trl_gap", "integrity", "Self-reported TRL (BlueInvest) minus the seed TRL estimate; large gaps need checking.", "levels", "medium", "recommended", "blueinvest_profile, readiness_assessments"),
    ("board_size", "founders", "Current directors / board members (Companies House directors, SEC Form D directors, PDL board titles).", "people", "medium", "recommended", "uk_companies_house, sec_form_d_document, pdl_person_search"),
    ("technical_open_roles", "momentum", "Open engineering / science / R&D roles.", "jobs", "medium", "recommended", "job_boards, serpapi_google_jobs"),
    ("commercial_open_roles", "momentum", "Open sales / business development / marketing / customer roles.", "jobs", "medium", "recommended", "job_boards, serpapi_google_jobs"),
    ("blueinvest_peer_count", "category", "Similar companies in the EU BlueInvest pipeline (similarity >= 0.1): competitor density.", "companies", "medium", "recommended", "blueinvest_pipeline"),
    ("peer_median_trl", "category", "Median TRL of the 10 most similar BlueInvest companies.", "1-9", "medium", "recommended", "blueinvest_pipeline"),
    ("trl_vs_peers", "category", "Own TRL (BlueInvest if listed, else seed estimate) minus the peer median TRL.", "levels", "medium", "recommended", "blueinvest_pipeline, readiness_assessments"),
    ("first_patent_granted", "momentum", "Was the company's first utility patent application granted? 1 granted, 0 abandoned/refused; 'pending' while undecided; 'unknown' for international (WO) filings, which never grant themselves (needs family data). Patent 'lottery' paper: first-patent approval predicts later funding and growth.", "flag", "medium", "user-list", "google patents"),
    ("first_patent_months_to_grant", "momentum", "Months from filing to grant for the first utility patent. Mostly reflects the patent office (EPO ~5 years, USPTO less): compare within one office.", "months", "low", "user-list", "google patents"),
    ("patents_pending", "momentum", "Patent applications still pending.", "patents", "low", "recommended", "google patents"),
    ("patents_abandoned", "momentum", "Applications abandoned, withdrawn, refused or lapsed for non-payment (WO 'ceased' excluded: it only ends the international phase).", "patents", "medium", "recommended", "google patents"),
    ("investor_count", "investors", "Number of investors: Form D count if filed, else distinct investors known.", "investors", "medium", "paper", "sec_form_d, funding_rounds"),
    ("lead_investors", "investors", "Lead investors across rounds.", None, "high", "user-list", "funding_rounds"),
    ("investor_quality_max", "investors", "Best investor tier score (analyst-curated, investor_tiers.json).", "0-1", "high", "paper", "investor_tiers.json"),
    ("investor_quality_mean", "investors", "Mean tier score across all known investors.", "0-1", "medium", "paper", "investor_tiers.json"),
    ("specialist_investor_share", "investors", "Share of investors that are ocean or climate specialists.", "0-1", "medium", "recommended", "investor_tiers.json"),
    ("follow_on_investors", "investors", "Investors appearing in more than one round of this startup.", "investors", "medium", "recommended", "funding_rounds"),
    ("founder_count", "founders", "Founders: directors appointed within 30 days of incorporation (UK), else beneficial owners.", "people", "medium", "paper", "uk_companies_house"),
    ("serial_founder_count", "founders", "Founders who directed another company before this one was incorporated.", "people", "medium", "paper", "uk_companies_house_officer"),
    ("prior_ventures_total", "founders", "Companies the founders directed before this one.", "companies", "medium", "paper", "uk_companies_house_officer"),
    ("prior_ventures_failed", "founders", "Of those, how many are dissolved, liquidated or in administration.", "companies", "medium", "recommended", "uk_companies_house_officer"),
    ("founder_retention", "founders", "Share of founders still serving as directors.", "0-1", "high", "recommended", "uk_companies_house"),
    ("officer_churn", "founders", "Resigned officers / all officers ever appointed.", "0-1", "medium", "recommended", "uk_companies_house"),
    ("category_tags", "category", "Tags used for peer similarity: sector, industry, YC tags, SIC codes, ocean impact areas, keywords.", "JSON", "medium", "paper", "seed, people_data_labs, yc_oss, uk_companies_house, startup_ocean_kpis"),
    ("top_peer", "category", "Most similar startup in the DB by weighted tag overlap.", None, "medium", "user-list", "derived"),
    ("headcount", "momentum", "Latest employee count.", "employees", "high", "user-list", "people_data_labs, yc_oss"),
    ("open_roles", "momentum", "Open job postings matched to the company.", "jobs", "medium", "recommended", "serpapi_google_jobs"),
    ("news_mentions_12m", "momentum", "News items naming the company in the last 12 months.", "items", "low", "recommended", "google_news_rss, gdelt_doc"),
    ("allotments_last_12m", "momentum", "UK share allotments in the last 12 months (raise cadence; often precedes announcements).", "filings", "medium", "recommended", "uk_sh01"),
    ("patent_count", "momentum", "Patents assigned to the company.", "patents", "medium", "user-list", "google patents / serpapi"),
    ("patents_granted", "momentum", "Of those, how many are granted.", "patents", "medium", "recommended", "google patents / serpapi"),
    ("grant_share", "rounds", "Share of announced funding that is non-dilutive (grants).", "0-1", "medium", "recommended", "funding_rounds"),
    ("company_age_years", "category", "Years since founding (curated year, else earliest registry date).", "years", "low", "user-list", "startups, uk_companies_house"),
    ("distress_flag", "risk", "1 if insolvency case, administration/liquidation status, or no active officers.", "flag", "high", "recommended", "uk_companies_house"),
    ("registry_status", "risk", "Registered company status.", None, "high", "recommended", "uk_companies_house, gleif_lei"),
    ("funding_total_spread", "integrity", "Max/min ratio between independent total-raised figures (1 = sources agree).", "x", "medium", "recommended", "derived"),
    ("founded_year_conflicts", "integrity", "Distinct founded-year values across sources, including the curated one.", "values", "low", "recommended", "field_suggestions"),
]


# ---------------------------------------------------------------------------
# Fetching: Companies House officers + SH01, SEC Form D
# ---------------------------------------------------------------------------
def download_pdf(url: str, dest: Path) -> bool:
    if dest.exists() and dest.stat().st_size > 0:
        return True
    dest.parent.mkdir(parents=True, exist_ok=True)
    key = os.environ.get("COMPANIES_HOUSE_KEY")
    if not key:
        return False
    p = subprocess.run(["curl", "-sS", "-L", "--max-time", "60", "-u", f"{key}:", "-H", "Accept: application/pdf",
                        "-o", str(dest), "-w", "%{http_code}", url], capture_output=True, text=True)
    ok = p.returncode == 0 and p.stdout.strip() == "200"
    if not ok and dest.exists():
        dest.unlink()
    return ok


def pdf_text(path: Path) -> str:
    try:
        from pypdf import PdfReader
    except ImportError:
        sys.exit("pypdf missing: run with Backend/.venv/bin/python or `pip install pypdf`")
    try:
        return "\n".join(page.extract_text() or "" for page in PdfReader(str(path)).pages)
    except Exception:  # noqa: BLE001  (corrupt or scanned PDF)
        return ""


ALLOT_RE = re.compile(r"Class of Shares:\s*(?P<cls>.+?)\s*Currency:\s*(?P<cur>[A-Z]{3}).*?Number allotted\s*(?P<n>[\d,]+).*?"
                      r"Nominal value of each share\s*(?P<nom>[\d.,]+).*?Amount paid:\s*(?P<paid>[\d.,]+)", re.S)


def parse_sh01(text: str) -> dict | None:
    """Return {'allotments': [...], 'total_shares': int, 'currency': str, 'from': date, 'to': date} or None if no text."""
    if "Shares Allotted" not in text:
        return None
    head, _, capital = text.partition("Statement of Capital")
    num = lambda s: float(s.replace(",", ""))  # noqa: E731
    allots = [{"share_class": " ".join(m["cls"].split()), "currency": m["cur"], "shares": int(num(m["n"])),
               "nominal": num(m["nom"]), "price": num(m["paid"])} for m in ALLOT_RE.finditer(head)]
    tot = re.search(r"Currency:\s*([A-Z]{3})\s*Total number of shares:\s*([\d,]+)", capital)
    period = re.findall(r"(\d{2}/\d{2}/\d{4})", head.split("Class of Shares")[0])
    d = lambda s: datetime.strptime(s, "%d/%m/%Y").date().isoformat()  # noqa: E731
    return {"allotments": allots, "total_shares": int(num(tot.group(2))) if tot else None, "currency": tot.group(1) if tot else None,
            "from": d(period[-2]) if len(period) >= 2 else None, "to": d(period[-1]) if period else None}


def is_priced(a: dict) -> bool:
    # Investment rounds pay a large premium over nominal; option exercises / founder shares are near nominal.
    return a["price"] >= max(20 * a["nominal"], 0.01) and a["shares"] * a["price"] >= 50_000


def fetch_uk(conn, st):
    row = conn.execute("SELECT external_id, details FROM startup_external_ids WHERE startup_id=? AND id_type='company_number'", (st["id"],)).fetchone()
    if not row:
        return
    num, det = row["external_id"], json.loads(row["details"] or "{}")
    created = parse_date(det.get("date_of_creation"))
    sid = st["id"]

    # Officers -> people, founders, prior ventures
    d, _ = fetch(conn, "uk_companies_house_company", sid, number=num, path="officers", items_per_page=100)
    for o in (d or {}).get("items", []):
        oid = ((o.get("links") or {}).get("officer") or {}).get("appointments", "").split("/")[2] if (o.get("links") or {}).get("officer") else None
        conn.execute("""INSERT INTO people (name, ch_officer_id, nationality, country_of_residence) VALUES (?,?,?,?)
                        ON CONFLICT(ch_officer_id) DO UPDATE SET name=excluded.name""",
                     (o["name"], oid, o.get("nationality"), o.get("country_of_residence")))
        pid = conn.execute("SELECT id FROM people WHERE ch_officer_id=?", (oid,)).fetchone()[0]
        appointed = parse_date(o.get("appointed_on"))
        founder = int(o.get("officer_role") == "director" and created is not None and appointed is not None and (appointed - created).days <= 30)
        conn.execute("""INSERT OR REPLACE INTO startup_people (startup_id, person_id, role, is_founder, appointed_on, resigned_on, source_name)
                        VALUES (?,?,?,?,?,?, 'uk_companies_house_company')""", (sid, pid, o.get("officer_role"), founder, o.get("appointed_on"), o.get("resigned_on")))
        if oid:
            a, _ = fetch(conn, "uk_companies_house_officer", sid, officer_id=oid, items_per_page=50)
            for ap in (a or {}).get("items", []):
                to = ap.get("appointed_to") or {}
                if to.get("company_number") == num:
                    continue
                conn.execute("""INSERT OR REPLACE INTO person_ventures (person_id, company_number, company_name, company_status, role, appointed_on, resigned_on, source_name)
                                VALUES (?,?,?,?,?,?,?, 'uk_companies_house_officer')""",
                             (pid, to.get("company_number"), to.get("company_name"), to.get("company_status"), ap.get("officer_role"), ap.get("appointed_on"), ap.get("resigned_on")))

    # SH01 allotments -> funding_events (rebuilt each run: rows without a share class would not dedupe on the UNIQUE key)
    conn.execute("DELETE FROM funding_events WHERE startup_id=? AND source_name='uk_sh01'", (sid,))
    d, f = fetch(conn, "uk_companies_house_company", sid, number=num, path="filing-history", category="capital", items_per_page=100)
    for it in (d or {}).get("items", []):
        if it.get("type") != "SH01":  # RP04SH01 second filings duplicate the original
            continue
        meta = (it.get("links") or {}).get("document_metadata")
        url = f"https://find-and-update.company-information.service.gov.uk{(it.get('links') or {}).get('self', '')}"
        parsed = None
        if meta:
            pdf = CACHE / f"{num}_{it.get('barcode') or it['transaction_id']}.pdf"
            if download_pdf(meta + "/content", pdf):
                parsed = parse_sh01(pdf_text(pdf))
        dv = it.get("description_values") or {}
        when = (parsed or {}).get("to") or dv.get("date") or it.get("date")
        if not parsed or not parsed["allotments"]:
            conn.execute("""INSERT OR REPLACE INTO funding_events (startup_id, event_date, source_name, event_type, details, source_url)
                            VALUES (?,?, 'uk_sh01', 'allotment_unparsed', ?, ?)""",
                         (sid, when, json.dumps({"reason": "no machine-readable text (paper filing?)", "capital": dv.get("capital")}), url))
            continue
        for a in parsed["allotments"]:
            priced = is_priced(a)
            conn.execute("""INSERT OR REPLACE INTO funding_events
                            (startup_id, event_date, source_name, event_type, amount, currency, share_class, shares_allotted, price_per_share,
                             total_shares_after, implied_post_money, details, source_url)
                            VALUES (?,?, 'uk_sh01', ?,?,?,?,?,?,?,?,?,?)""",
                         (sid, when, "priced_allotment" if priced else "nominal_allotment", round(a["shares"] * a["price"], 2), a["currency"],
                          a["share_class"], a["shares"], a["price"], parsed["total_shares"],
                          round(a["price"] * parsed["total_shares"], 2) if priced and parsed["total_shares"] else None,
                          json.dumps({"period_from": parsed["from"], "nominal": a["nominal"], "filed_on": it.get("date")}), url))
    conn.commit()


FORM_D_TAGS = ("entityName", "totalOfferingAmount", "totalAmountSold", "totalNumberAlreadyInvested", "isAmendment", "industryGroupType")


def fetch_form_d(conn, st):
    row = conn.execute("SELECT external_id FROM startup_external_ids WHERE startup_id=? AND id_type='sec_cik'", (st["id"],)).fetchone()
    if not row:
        return
    cik, sid = row[0], st["id"]
    conn.execute("DELETE FROM funding_events WHERE startup_id=? AND source_name='sec_form_d'", (sid,))  # rebuilt each run
    seen_people: dict[str, dict] = {}  # name -> {"roles": set, "first": date, "last": date}
    filing_dates: list[str] = []
    sub, _ = fetch(conn, "sec_edgar_submissions", sid, cik=cik)
    recent = ((sub or {}).get("filings") or {}).get("recent") or {}
    for form, acc, filed in zip(recent.get("form", []), recent.get("accessionNumber", []), recent.get("filingDate", [])):
        if form not in ("D", "D/A"):
            continue
        xml, _ = fetch(conn, "sec_form_d_document", sid, cik=cik, accession=acc.replace("-", ""))
        if not isinstance(xml, str):
            continue
        g = {t: (re.findall(f"<{t}>(.*?)</{t}>", xml, re.S) or [None])[0] for t in FORM_D_TAGS}
        first_sale = re.search(r"<dateOfFirstSale>\s*<value>(.*?)</value>", xml, re.S)
        persons = []
        for blk in re.findall(r"<relatedPersonInfo>(.*?)</relatedPersonInfo>", xml, re.S):
            first = (re.findall(r"<firstName>(.*?)</firstName>", blk) or [""])[0]
            last = (re.findall(r"<lastName>(.*?)</lastName>", blk) or [""])[0]
            name = f"{first} {last}".strip()
            persons.append(name)
            p = seen_people.setdefault(name, {"roles": set(), "first": filed, "last": filed})
            p["roles"] |= {r.strip().lower() for r in re.findall(r"<relationship>(.*?)</relationship>", blk)}
            p["first"], p["last"] = min(p["first"], filed), max(p["last"], filed)
        filing_dates.append(filed)
        amt = lambda k: float(g[k]) if g[k] and g[k].replace(".", "").isdigit() else None  # noqa: E731  ("Indefinite" -> None)
        conn.execute("""INSERT OR REPLACE INTO funding_events (startup_id, event_date, source_name, event_type, amount, currency, investor_count, details, source_url)
                        VALUES (?,?, 'sec_form_d', 'form_d', ?, 'USD', ?, ?, ?)""",
                     (sid, first_sale.group(1) if first_sale else filed, amt("totalAmountSold"),
                      int(g["totalNumberAlreadyInvested"]) if (g["totalNumberAlreadyInvested"] or "").isdigit() else None,
                      json.dumps({"form": form, "filed_on": filed, "accession": acc, "offering": amt("totalOfferingAmount"),
                                  "is_amendment": g["isAmendment"], "industry": g["industryGroupType"], "related_persons": persons}),
                      f"https://www.sec.gov/Archives/edgar/data/{cik}/{acc.replace('-', '')}/"))
    # Roles from Form D: directors and executive officers per filing. Absent from the latest filing = left (proxy).
    conn.execute("DELETE FROM startup_people WHERE startup_id=? AND source_name='sec_form_d_document'", (sid,))
    latest = max(filing_dates) if filing_dates else None
    for name, p in seen_people.items():
        conn.execute("INSERT INTO people (name) SELECT ? WHERE NOT EXISTS (SELECT 1 FROM people WHERE name=? AND ch_officer_id IS NULL)", (name, name))
        pid = conn.execute("SELECT id FROM people WHERE name=? AND ch_officer_id IS NULL", (name,)).fetchone()[0]
        for role in sorted(p["roles"]) or ["related person"]:
            conn.execute("""INSERT OR REPLACE INTO startup_people (startup_id, person_id, role, is_founder, appointed_on, resigned_on, source_name)
                            VALUES (?,?,?,0,?,?, 'sec_form_d_document')""",
                         (sid, pid, role, p["first"], None if p["last"] == latest else p["last"]))
    conn.commit()


# ---------------------------------------------------------------------------
# Local builds: announced rounds, PDL aggregate, investors
# ---------------------------------------------------------------------------
PARTICIPANT_RE = [re.compile(r"\bWith ([^.]+)\."), re.compile(r"Co-investors?: ([^.]+)\."),
                  re.compile(r"([A-Z][^.;]+?) participated"), re.compile(r"([A-Z][^.;]+?) previously invested"), re.compile(r"; ([A-Z][\w\- ]+) anchor")]


def split_names(s: str) -> list[str]:
    out = []
    for part in re.split(r",|;| and ", s):
        part = re.sub(r"^(Seed II first close|Pre-Series A raise to commercialise)\s*", "", part.strip()).strip()
        if part and part[0].isupper() and len(part) > 2:
            out.append(part)
    return out


def build_local(conn):
    tiers = json.loads((HERE / "investor_tiers.json").read_text())
    alias = tiers.get("aliases", {})
    conn.execute("DELETE FROM funding_events WHERE source_name IN ('funding_rounds','people_data_labs')")
    conn.execute("DELETE FROM startup_investors")
    for r in conn.execute("SELECT * FROM funding_rounds").fetchall():
        if r["announced_on"]:
            conn.execute("""INSERT OR REPLACE INTO funding_events (startup_id, event_date, source_name, event_type, round_label, amount, currency, details, source_url)
                            VALUES (?,?, 'funding_rounds', 'announced_round', ?,?,?,?,?)""",
                         (r["startup_id"], r["announced_on"], r["round_type"], r["amount"], r["currency"],
                          json.dumps({"lead_investors": r["lead_investors"], "notes": r["notes"]}), r["source_url"]))
        named = [(n, "lead") for n in split_names(r["lead_investors"] or "")]
        for rx in PARTICIPANT_RE:
            for m in rx.finditer(r["notes"] or ""):
                named += [(n, "participant") for n in split_names(m.group(1))]
        for name, role in named:
            name = alias.get(name, name)
            spec = tiers["investors"].get(name, {})
            kind = spec.get("kind", "unknown")
            score = spec.get("score", tiers["kind_scores"].get(kind, tiers["kind_scores"]["unknown"]))
            conn.execute("""INSERT INTO investors (name, kind, tier_score) VALUES (?,?,?)
                            ON CONFLICT(name) DO UPDATE SET kind=excluded.kind, tier_score=excluded.tier_score""", (name, kind, score))
            iid = conn.execute("SELECT id FROM investors WHERE name=?", (name,)).fetchone()[0]
            conn.execute("""INSERT INTO startup_investors (startup_id, investor_id, role, first_seen, rounds, source_name) VALUES (?,?,?,?,1,'funding_rounds')
                            ON CONFLICT(startup_id, investor_id, role) DO UPDATE SET rounds=rounds+1,
                              first_seen=MIN(COALESCE(first_seen, excluded.first_seen), COALESCE(excluded.first_seen, first_seen))""",
                         (r["startup_id"], iid, role, r["announced_on"]))
    for s in conn.execute("SELECT startup_id, observed_on, value, details FROM startup_signals WHERE unit='usd_raised'").fetchall():
        det = json.loads(s["details"] or "{}")
        conn.execute("""INSERT OR REPLACE INTO funding_events (startup_id, event_date, source_name, event_type, round_label, amount, currency, details, match_confidence)
                        VALUES (?,?, 'people_data_labs', 'aggregate', ?,?, 'USD', ?, 'medium')""",
                     (s["startup_id"], s["observed_on"] or AS_OF, det.get("latest_stage"), s["value"], json.dumps(det)))
    conn.commit()


# ---------------------------------------------------------------------------
# Features
# ---------------------------------------------------------------------------
STOP = set("the and for with from that this into their our are its has have been which made make based using offshore company companies "
           "builds develops products product other scale data real time each trip".split())
ITEM_W = {"sector": 2.0, "industry": 2.0, "bisector": 2.0, "yc": 1.5, "sic": 1.5, "impact": 1.5, "cpc": 1.0, "field": 1.0, "kw": 1.0}


def tags_for(conn, st) -> dict[str, float]:
    t = {f"sector:{norm(st['sector'])}": ITEM_W["sector"]}
    for (det,) in conn.execute("SELECT details FROM startup_external_ids WHERE startup_id=? AND id_type IN ('pdl_id','yc_slug','company_number')", (st["id"],)):
        d = json.loads(det or "{}")
        if d.get("industry_v2"):
            t[f"industry:{norm(d['industry_v2'])}"] = ITEM_W["industry"]
        for tag in d.get("tags") or []:
            t[f"yc:{norm(tag)}"] = ITEM_W["yc"]
        for code in d.get("sic_codes") or []:
            t[f"sic:{code[:2]}"] = ITEM_W["sic"]  # 2-digit SIC division
    for (code,) in conn.execute("SELECT DISTINCT substr(kpi_code,1,1) FROM startup_ocean_kpis WHERE startup_id=? AND evidence_level>0", (st["id"],)):
        t[f"impact:{code}"] = ITEM_W["impact"]
    for (cls,) in conn.execute("SELECT DISTINCT substr(cpc_code,1,4) FROM patent_classes WHERE startup_id=? AND cpc_code NOT LIKE 'Y10%'", (st["id"],)):
        t[f"cpc:{cls}"] = ITEM_W["cpc"]  # CPC subclass, e.g. A61K
    for (cats,) in conn.execute("SELECT categories FROM eu_grants WHERE startup_id=?", (st["id"],)):
        for c in json.loads(cats or "[]"):
            t[f"field:{norm(c)}"] = ITEM_W["field"]  # CORDIS euroSciVoc field
    for (sec,) in conn.execute("SELECT sector FROM blueinvest_profiles WHERE startup_id=? AND sector IS NOT NULL", (st["id"],)):
        t[f"bisector:{norm(sec)}"] = ITEM_W["bisector"]
    words = re.findall(r"[a-z]{4,}", f"{st['tagline']} {st['description']}".lower())
    for w in words:
        if w not in STOP:
            t[f"kw:{w.rstrip('s')}"] = ITEM_W["kw"]
    return t


def weighted_jaccard(a: dict, b: dict) -> tuple[float, list[str]]:
    keys = set(a) | set(b)
    inter = sum(min(a.get(k, 0), b.get(k, 0)) for k in keys)
    union = sum(max(a.get(k, 0), b.get(k, 0)) for k in keys)
    shared = sorted(k for k in set(a) & set(b))
    return (inter / union if union else 0.0), shared


def merge_dates(dates: list[date], window_days=90) -> list[date]:
    out = []
    for d in sorted(dates):
        if not out or (d - out[-1]).days > window_days:
            out.append(d)
    return out


def compute(conn):
    conn.execute("DELETE FROM feature_definitions WHERE name NOT IN (SELECT DISTINCT feature FROM startup_features)")
    for f in FEATURES:
        conn.execute("""INSERT INTO feature_definitions (name, feature_group, description, unit, importance, origin, sources) VALUES (?,?,?,?,?,?,?)
                        ON CONFLICT(name) DO UPDATE SET feature_group=excluded.feature_group, description=excluded.description, unit=excluded.unit,
                          importance=excluded.importance, origin=excluded.origin, sources=excluded.sources""", f)
    conn.execute("DELETE FROM startup_features WHERE as_of=?", (AS_OF,))
    conn.execute("DELETE FROM startup_peers")
    startups = conn.execute("SELECT * FROM startups ORDER BY id").fetchall()
    tagsets = {st["id"]: tags_for(conn, st) for st in startups}

    for st in startups:
        sid = st["id"]
        out: dict[str, tuple] = {}

        def put(name, num=None, text=None, evidence=None):
            if num is None and text is None:
                return  # missing stays missing
            out[name] = (num, text, json.dumps(evidence, default=str) if evidence is not None else None)

        def put_na(name, reason):
            out[name] = (None, "not-applicable", json.dumps({"reason": reason}))  # known not to apply, unlike missing

        ev = conn.execute("SELECT * FROM funding_events WHERE startup_id=? ORDER BY event_date", (sid,)).fetchall()
        announced = [e for e in ev if e["event_type"] == "announced_round"]
        priced = [e for e in ev if e["event_type"] == "priced_allotment"]
        formd = [e for e in ev if e["event_type"] == "form_d"]
        pdl = next((e for e in ev if e["event_type"] == "aggregate"), None)

        # Form D: one offering per first-sale date; keep the latest filing (amendments update totals)
        offerings = {}
        for e in sorted(formd, key=lambda e: json.loads(e["details"] or "{}").get("filed_on") or ""):
            offerings[e["event_date"]] = e  # later filings (D/A amendments) replace earlier ones
        # priced SH01 allotments grouped into rounds (90-day window)
        # A round = priced allotments at the same price (within 2%) with no gap over 180 days.
        # Price matters: Oceanium's 2025 GBP 0.0211 allotment came 67 days after one at GBP 1.76.
        groups = []
        for e in priced:
            d = parse_date(e["event_date"])
            g = next((g for g in reversed(groups) if abs(e["price_per_share"] / g["price"] - 1) <= 0.02 and (d - g["end"]).days <= 180), None)
            if g:
                g["end"], g["amount"] = d, g["amount"] + (e["amount"] or 0)
                g["events"].append(e)
            else:
                groups.append({"start": d, "end": d, "price": e["price_per_share"], "amount": e["amount"] or 0, "currency": e["currency"], "events": [e]})
        priced_rounds = sorted([g for g in groups if g["amount"] >= 100_000], key=lambda g: g["start"])  # tiny ones: conversions, top-ups

        cands = {
            "announced_rounds": sum(usd(e["amount"], e["currency"]) or 0 for e in announced) or None,
            "sec_form_d": sum(e["amount"] or 0 for e in offerings.values()) or None,
            "uk_sh01_priced": sum(usd(g["amount"], g["currency"]) or 0 for g in priced_rounds) or None,
            "people_data_labs": pdl["amount"] if pdl else None,
        }
        vals = {k: round(v) for k, v in cands.items() if v}
        if vals:
            put("total_raised_usd", max(vals.values()), evidence=vals)
            if len(vals) > 1:
                put("funding_total_spread", round(max(vals.values()) / min(vals.values()), 2), evidence=vals)

        pdl_det = json.loads(pdl["details"] or "{}") if pdl else {}
        counts = {"announced_rounds": len(announced), "uk_sh01_priced_rounds": len(priced_rounds), "sec_form_d_offerings": len(offerings),
                  "people_data_labs": pdl_det.get("rounds")}
        counts = {k: v for k, v in counts.items() if v}
        if counts:
            put("round_count", max(counts.values()), evidence=counts)

        round_dates = [parse_date(e["event_date"]) for e in announced] + [g["start"] for g in priced_rounds] + \
                      [parse_date(d) for d in offerings] + ([parse_date(pdl["event_date"])] if pdl else [])
        raw_dates = [d for d in round_dates if d]
        round_dates = merge_dates(raw_dates)
        if round_dates:
            last = max(raw_dates)  # merging keeps a cluster's first date; recency needs the latest
            put("last_round_date", text=last.isoformat(), evidence={"dates": [d.isoformat() for d in round_dates]})
            m = months_between(last, TODAY)
            put("months_since_last_round", round(m, 1))
            put("no_round_24m", 1.0 if (TODAY - last).days > 730 else 0.0, evidence={"last_round": last.isoformat(), "rule": "730 days (Potanin et al. 2023)"})
            if len(round_dates) > 1:
                gaps = [months_between(a, b) for a, b in zip(round_dates, round_dates[1:])]
                put("median_months_between_rounds", round(statistics.median(gaps), 1), evidence={"gaps_months": [round(g, 1) for g in gaps]})
        last_type = (announced[-1]["round_label"] if announced else None) or pdl_det.get("latest_stage")
        if pdl_det.get("latest_stage") and pdl and announced and parse_date(pdl["event_date"]) and parse_date(pdl["event_date"]) > parse_date(announced[-1]["event_date"]):
            last_type = pdl_det["latest_stage"]
        put("last_round_type", text=last_type)

        if priced_rounds:
            latest = priced_rounds[-1]["events"][-1]
            put("latest_price_per_share", latest["price_per_share"], evidence={"date": latest["event_date"], "class": latest["share_class"], "currency": latest["currency"]})
            put("implied_post_money", latest["implied_post_money"], evidence={"date": latest["event_date"], "price": latest["price_per_share"],
                                                                            "total_shares": latest["total_shares_after"], "currency": latest["currency"]})
            if len(priced_rounds) == 1:
                put_na("valuation_step_up", "only one priced round on file")
                put_na("down_round_flag", "only one priced round on file")
            if len(priced_rounds) > 1:
                prev, cur = priced_rounds[-2]["price"], priced_rounds[-1]["price"]
                put("valuation_step_up", round(cur / prev, 4), evidence={"previous": [priced_rounds[-2]["start"], prev], "latest": [priced_rounds[-1]["start"], cur]})
                downs = [(a["start"].isoformat(), a["price"], b["start"].isoformat(), b["price"]) for a, b in zip(priced_rounds, priced_rounds[1:]) if b["price"] < a["price"] * 0.98]
                put("down_round_flag", 1.0 if downs else 0.0, evidence={"down_rounds": downs,
                    "round_prices": [(g["start"].isoformat(), g["price"], round(g["amount"])) for g in priced_rounds]})
        cutoff = TODAY.replace(year=TODAY.year - 1)
        n12 = sum(1 for e in ev if e["source_name"] == "uk_sh01" and parse_date(e["event_date"]) and parse_date(e["event_date"]) >= cutoff)
        if any(e["source_name"] == "uk_sh01" for e in ev):
            put("allotments_last_12m", n12)

        grants = sum(usd(e["amount"], e["currency"]) or 0 for e in announced if e["round_label"] == "grant")
        tot_ann = cands["announced_rounds"]
        if tot_ann:
            put("grant_share", round(grants / tot_ann, 3), evidence={"grant_usd": round(grants), "announced_usd": round(tot_ann)})

        # investors
        inv = conn.execute("""SELECT i.name, i.kind, i.tier_score, si.role, si.rounds FROM startup_investors si JOIN investors i ON i.id=si.investor_id
                              WHERE si.startup_id=?""", (sid,)).fetchall()
        if inv:
            scores = [r["tier_score"] for r in inv]
            put("investor_quality_max", max(scores), evidence={r["name"]: [r["kind"], r["tier_score"]] for r in inv})
            put("investor_quality_mean", round(statistics.mean(scores), 3))
            put("specialist_investor_share", round(sum(r["kind"] in ("ocean-vc", "climate-vc") for r in inv) / len(inv), 3))
            put("follow_on_investors", sum(1 for r in inv if r["rounds"] > 1), evidence=[r["name"] for r in inv if r["rounds"] > 1])
            leads = sorted({r["name"] for r in inv if r["role"] == "lead"})
            put("lead_investors", text="; ".join(leads) if leads else None)
        ic = {}
        if offerings:
            latest_off = offerings[max(offerings)]
            if latest_off["investor_count"]:
                ic["sec_form_d_latest_offering"] = latest_off["investor_count"]
        if inv:
            ic["known_investors"] = len({r["name"] for r in inv})
        if ic:
            put("investor_count", ic.get("sec_form_d_latest_offering", ic.get("known_investors")), evidence=ic)

        # founders (UK officers if present, else PDL; Form D adds US boards)
        allp = conn.execute("SELECT sp.*, p.name, p.education FROM startup_people sp JOIN people p ON p.id=sp.person_id WHERE sp.startup_id=?", (sid,)).fetchall()
        src = next((s_ for s_ in ("uk_companies_house_company", "people_data_labs")
                    if any(p["is_founder"] and p["source_name"] == s_ for p in allp)), None)
        reg = conn.execute("SELECT details FROM startup_external_ids WHERE startup_id=? AND id_type='company_number'", (sid,)).fetchone()
        created = parse_date(json.loads(reg["details"] or "{}").get("date_of_creation")) if reg else None
        if not created and st["founded_year"]:
            created = date(st["founded_year"], 1, 1)
        if src:
            rows = [p for p in allp if p["source_name"] == src]
            founders = {}
            for p in rows:
                if p["is_founder"]:
                    founders.setdefault(p["person_id"], p)
            if not created:
                created = min(filter(None, (parse_date(p["appointed_on"]) for p in founders.values())), default=None)
            put("founder_count", len(founders), evidence={"source": src, "founders": [p["name"] for p in founders.values()]})
            serial, prior_total, prior_failed, known_status, detail, other = 0, 0, 0, False, {}, {}
            for pid, p in founders.items():
                ventures = conn.execute("SELECT * FROM person_ventures WHERE person_id=?", (pid,)).fetchall()
                prior = [v for v in ventures if created and parse_date(v["appointed_on"]) and parse_date(v["appointed_on"]) < created
                         and (v["source_name"] != "people_data_labs" or re.search(r"founder|owner", v["role"] or "", re.I))
                         and not re.search(r"entrepreneurs first|y combinator|antler|techstars", v["company_name"] or "", re.I)]
                # UK: any earlier directorship counts. PDL: only founder/owner roles (an earlier CEO job at an airline is not a venture).
                serial += bool(prior)
                prior_total += len(prior)
                known_status |= any(v["company_status"] for v in prior)
                prior_failed += sum(1 for v in prior if (v["company_status"] or "") in ("dissolved", "liquidation", "administration", "receivership", "insolvency-proceedings"))
                detail[p["name"]] = [f"{v['company_name']} ({v['role']}, from {v['appointed_on']})" for v in prior]
                other[p["name"]] = [f"{v['company_name']} ({v['company_status'] or v['role']}, from {v['appointed_on']})" for v in ventures]
            put("serial_founder_count", serial, evidence={"source": src, "prior_ventures": detail})
            put("prior_ventures_total", prior_total, evidence=detail)
            if known_status or not prior_total:
                put("prior_ventures_failed", prior_failed)  # PDL has no company status: unknown, not zero
            put("founder_other_ventures", sum(len(v) for v in other.values()), evidence=other)
            if founders:
                active = [pid for pid in founders if any(r["person_id"] == pid and not r["resigned_on"] for r in rows)]
                put("founder_retention", round(len(active) / len(founders), 3),
                    evidence={"active": [founders[p]["name"] for p in active], "left": [founders[p]["name"] for p in founders if p not in active]})
        uk = [p for p in allp if p["source_name"] == "uk_companies_house_company"]
        if uk:
            put("officer_churn", round(sum(1 for p in uk if p["resigned_on"]) / len(uk), 3))
        board = {p["name"] for p in allp if not p["resigned_on"] and (
            (p["source_name"] in ("uk_companies_house_company", "sec_form_d_document") and p["role"] == "director")
            or (p["source_name"] == "people_data_labs" and re.search(r"chair|board", p["role"] or "", re.I)))}
        if any(p["source_name"] in ("uk_companies_house_company", "sec_form_d_document", "people_data_labs") for p in allp):
            put("board_size", len(board), evidence=sorted(board))
        people = uk  # used by the distress check below

        # momentum
        hc = conn.execute("SELECT value, source_name, observed_on FROM startup_signals WHERE startup_id=? AND unit='employees' ORDER BY observed_on DESC, source_name='people_data_labs' DESC LIMIT 1", (sid,)).fetchone()
        if hc:
            put("headcount", hc["value"], evidence={"source": hc["source_name"], "observed_on": hc["observed_on"]})
        job_rows = conn.execute("SELECT source_name, details FROM startup_signals WHERE startup_id=? AND signal_type='job'", (sid,)).fetchall()
        if conn.execute("SELECT 1 FROM raw_fetches WHERE startup_id=? AND source_name IN ('serpapi_google_jobs','job_boards') AND status='ok'", (sid,)).fetchone():
            board_jobs = [r for r in job_rows if r["source_name"] == "job_boards"]
            use = board_jobs or job_rows  # the ATS board is the company's own list; Google Jobs duplicates it
            cats = [json.loads(r["details"] or "{}").get("category") for r in use]
            put("open_roles", len(use), evidence={"source": "job_boards" if board_jobs else "serpapi_google_jobs"})
            put("technical_open_roles", cats.count("technical"))
            put("commercial_open_roles", cats.count("commercial"))
        news = conn.execute("SELECT COUNT(*) FROM startup_signals WHERE startup_id=? AND signal_type='news' AND observed_on>=?", (sid, cutoff.isoformat())).fetchone()[0]
        put("news_mentions_12m", news)
        pat = conn.execute("SELECT COUNT(*), SUM(json_extract(details,'$.grant_date') IS NOT NULL) FROM startup_signals WHERE startup_id=? AND signal_type='patent'", (sid,)).fetchone()
        if conn.execute("SELECT 1 FROM raw_fetches WHERE startup_id=? AND source_name LIKE '%patents%' AND status='ok'", (sid,)).fetchone():
            put("patent_count", pat[0])
            put("patents_granted", pat[1] or 0)
            pats = []
            for r in conn.execute("SELECT title, details FROM startup_signals WHERE startup_id=? AND signal_type='patent'", (sid,)):
                d = json.loads(r["details"] or "{}")
                pats.append({"number": r["title"].split(":")[0].strip(), "filed": d.get("filing_date"), "granted": d.get("grant_date"),
                             "status": (d.get("legal_status") or "").strip().lower()})
            is_wo = lambda p: p["number"].startswith("WO")  # noqa: E731
            dropped = lambda p: p["status"] in ("abandoned", "withdrawn", "refused", "rejected", "expired - fee related") or (p["status"] == "ceased" and not is_wo(p))  # noqa: E731
            put("patents_pending", sum(1 for p in pats if p["status"] == "pending"))
            put("patents_abandoned", sum(1 for p in pats if dropped(p)), evidence=[p["number"] for p in pats if dropped(p)])
            utility = sorted((p for p in pats if p["filed"] and not re.match(r"US-?D\d", p["number"])), key=lambda p: p["filed"])  # design patents (USD...) excluded
            if not pats:
                put_na("first_patent_granted", "no patents found")
                put_na("first_patent_months_to_grant", "no patents found")
            elif utility:
                first = utility[0]
                ev = {"patent": first["number"], "office": first["number"][:2], "filed": first["filed"], "granted": first["granted"], "status": first["status"]}
                if first["granted"]:
                    put("first_patent_granted", 1.0, "granted", evidence=ev)
                    put("first_patent_months_to_grant", round(months_between(parse_date(first["filed"]), parse_date(first["granted"])), 1), evidence=ev)
                elif dropped(first):
                    put("first_patent_granted", 0.0, "abandoned", evidence=ev)
                    put_na("first_patent_months_to_grant", "first patent was not granted")
                elif is_wo(first) and first["status"] == "ceased":
                    put("first_patent_granted", None, "unknown", evidence={**ev, "why": "WO international phase ended; whether national filings were granted needs family data"})
                else:
                    put("first_patent_granted", None, "pending", evidence=ev)  # undecided: neither 1 nor 0

        # age, risk, integrity
        reg = conn.execute("""SELECT details FROM startup_external_ids WHERE startup_id=? AND id_type IN ('company_number','siren','no_orgnr','lei')
                              ORDER BY CASE id_type WHEN 'company_number' THEN 0 WHEN 'siren' THEN 1 WHEN 'no_orgnr' THEN 2 ELSE 3 END LIMIT 1""", (sid,)).fetchone()
        regd = json.loads(reg["details"] or "{}") if reg else {}
        year = st["founded_year"] or (int(regd.get("date_of_creation", regd.get("registered_on", ""))[:4]) if (regd.get("date_of_creation") or regd.get("registered_on")) else None)
        if year:
            age = TODAY.year - year + 0.5
            put("company_age_years", age, evidence={"founded_year": year, "source": "startups.founded_year" if st["founded_year"] else "registry"})
            if out.get("total_raised_usd"):
                put("funding_velocity_usd_per_year", round(out["total_raised_usd"][0] / age))
        status = regd.get("status")
        if status:
            put("registry_status", text=status.lower())
        insolv = conn.execute("SELECT COUNT(*) FROM startup_signals WHERE startup_id=? AND unit='insolvency'", (sid,)).fetchone()[0]
        if people or status:
            no_officers = bool(people) and all(p["resigned_on"] for p in people)
            distress = int(insolv > 0 or no_officers or (status or "").lower() in
                           ("administration", "liquidation", "receivership", "insolvency-proceedings", "dissolved", "closed", "bankrupt"))
            put("distress_flag", distress, evidence={"insolvency_cases": insolv, "status": status, "no_active_officers": no_officers})
        years = {str(st["founded_year"])} if st["founded_year"] else set()
        years |= {r[0] for r in conn.execute("SELECT value FROM field_suggestions WHERE startup_id=? AND field='founded_year' AND status!='rejected'", (sid,))}
        if years:
            put("founded_year_conflicts", len(years), evidence=sorted(years))

        # EU grants (CORDIS)
        grants = conn.execute("SELECT * FROM eu_grants WHERE startup_id=?", (sid,)).fetchall()
        if conn.execute("SELECT 1 FROM raw_fetches WHERE startup_id=? AND source_name='cordis_projects' AND status='ok'", (sid,)).fetchone():
            total_eu = sum(g["ec_contribution"] or 0 for g in grants)
            put("eu_grants_total_eur", round(total_eu, 2), evidence={g["acronym"]: [g["role"], g["ec_contribution"]] for g in grants})
            put("eu_projects_count", len({g["project_id"] for g in grants}))
            put("eu_projects_funded", len({g["project_id"] for g in grants if (g["ec_contribution"] or 0) > 0}))
            put("eu_coordinator_count", sum(1 for g in grants if g["role"] == "coordinator"), evidence=[g["acronym"] for g in grants if g["role"] == "coordinator"])
            put("eic_or_sme_instrument", float(any(g["is_eic"] for g in grants)), evidence=[g["acronym"] for g in grants if g["is_eic"]])
            put("mission_ocean_grant", float(any(g["is_mission_ocean"] for g in grants)), evidence=[g["acronym"] for g in grants if g["is_mission_ocean"]])
            put("eu_active_projects", sum(1 for g in grants if g["status"] == "SIGNED" and (g["end_date"] or "") >= AS_OF))
            put("eu_consortium_links", sum(g["partners"] or 0 for g in grants))
            if grants:
                put("eu_first_grant_year", min(int(g["start_date"][:4]) for g in grants if g["start_date"]))
                put("cordis_sme_confirmed", float(any(g["sme"] for g in grants)))
            else:
                put_na("eu_first_grant_year", "no EU-funded projects found in CORDIS")
                put_na("cordis_sme_confirmed", "not a CORDIS participant")
            if out.get("total_raised_usd") and not total_eu:
                put("grant_to_equity_ratio", 0.0, evidence={"eu_grants_usd": 0, "total_raised_usd": out["total_raised_usd"][0]})
            if out.get("total_raised_usd") and total_eu:
                put("grant_to_equity_ratio", round(usd(total_eu, "EUR") / out["total_raised_usd"][0], 3),
                    evidence={"eu_grants_usd": round(usd(total_eu, "EUR")), "total_raised_usd": out["total_raised_usd"][0]})

        # ocean patent classes
        pc = conn.execute("""SELECT publication_number, MAX(ocean_group IS NOT NULL) ocean, GROUP_CONCAT(DISTINCT ocean_group) groups
                             FROM patent_classes WHERE startup_id=? GROUP BY publication_number""", (sid,)).fetchall()
        if pc:
            n_ocean = sum(r["ocean"] for r in pc)
            put("ocean_patent_count", n_ocean, evidence={r["publication_number"]: r["groups"] for r in pc if r["ocean"]})
            put("ocean_patent_share", round(n_ocean / len(pc), 3))
            groups = sorted({g for r in pc if r["groups"] for g in r["groups"].split(",")})
            put("ocean_tech_groups", text=json.dumps(groups))

        # BlueInvest pipeline
        if conn.execute("SELECT 1 FROM blueinvest_profiles LIMIT 1").fetchone():
            bi = conn.execute("SELECT * FROM blueinvest_profiles WHERE startup_id=? ORDER BY trl DESC LIMIT 1", (sid,)).fetchone()
            put("blueinvest_listed", 1.0 if bi else 0.0, evidence={"profile": bi["url"]} if bi else None)
            if not bi:
                for nm in ("blueinvest_trl", "blueinvest_funding_sought_eur", "blueinvest_sector", "trl_gap"):
                    put_na(nm, "not in the BlueInvest pipeline")
            if bi:
                put("blueinvest_trl", bi["trl"], evidence={"trl_text": bi["trl_text"]})
                put("blueinvest_funding_sought_eur", bi["funding_sought_eur"], evidence={"text": (bi["financial_needs"] or "")[:400]})
                put("blueinvest_sector", text=bi["sector"])
                est = conn.execute("SELECT trl FROM readiness_assessments WHERE startup_id=? ORDER BY assessed_on DESC, id DESC LIMIT 1", (sid,)).fetchone()
                if bi["trl"] and est:
                    put("trl_gap", bi["trl"] - est["trl"], evidence={"blueinvest_trl": bi["trl"], "seed_estimate_trl": est["trl"]})

        # competitor universe (BlueInvest)
        xp = conn.execute("SELECT name, similarity, trl FROM startup_external_peers WHERE startup_id=? ORDER BY similarity DESC", (sid,)).fetchall()
        if conn.execute("SELECT 1 FROM blueinvest_profiles LIMIT 1").fetchone():
            put("blueinvest_peer_count", sum(1 for r in xp if r["similarity"] >= 0.1), evidence=[[r["name"], r["similarity"]] for r in xp[:5]])
            trls = [r["trl"] for r in xp if r["trl"]]
            if trls:
                med = statistics.median(trls)
                put("peer_median_trl", med, evidence={"peer_trls": trls})
                own = out.get("blueinvest_trl", (None,))[0]
                if own is None:
                    est = conn.execute("SELECT trl FROM readiness_assessments WHERE startup_id=? ORDER BY assessed_on DESC, id DESC LIMIT 1", (sid,)).fetchone()
                    own = est["trl"] if est else None
                if own is not None:
                    put("trl_vs_peers", own - med, evidence={"own_trl": own, "peer_median": med})

        # category + peers
        put("category_tags", text=json.dumps(sorted(tagsets[sid])))
        peers = []
        for other in startups:
            if other["id"] == sid:
                continue
            sim, shared = weighted_jaccard(tagsets[sid], tagsets[other["id"]])
            if sim > 0:
                peers.append((sim, other, shared))
                conn.execute("INSERT INTO startup_peers (startup_id, peer_id, similarity, shared_tags) VALUES (?,?,?,?)",
                             (sid, other["id"], round(sim, 4), json.dumps(shared)))
        if peers:
            sim, other, shared = max(peers, key=lambda x: x[0])
            put("top_peer", round(sim, 3), other["slug"], evidence=shared)

        for name, (num, text, evid) in out.items():
            conn.execute("INSERT INTO startup_features (startup_id, feature, as_of, value_num, value_text, evidence) VALUES (?,?,?,?,?,?)",
                         (sid, name, AS_OF, num, text, evid))
    conn.commit()


def main(argv):
    conn = ingest.open_db()
    if "--offline" not in argv:
        for st in conn.execute("SELECT * FROM startups ORDER BY id").fetchall():
            print(f"-> {st['name']}")
            fetch_uk(conn, st)
            fetch_form_d(conn, st)
    build_local(conn)
    compute(conn)
    n = conn.execute("SELECT COUNT(*) FROM startup_features WHERE as_of=?", (AS_OF,)).fetchone()[0]
    print(f"features: {n} values for {AS_OF}; events: {conn.execute('SELECT COUNT(*) FROM funding_events').fetchone()[0]}; "
          f"people: {conn.execute('SELECT COUNT(*) FROM people').fetchone()[0]}; ventures: {conn.execute('SELECT COUNT(*) FROM person_ventures').fetchone()[0]}")


if __name__ == "__main__":
    main(sys.argv[1:])
