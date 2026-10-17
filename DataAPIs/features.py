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

    # SH01 allotments -> funding_events
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
        persons = [f"{a} {b}" for a, b in re.findall(r"<relatedPersonName>.*?<firstName>(.*?)</firstName>.*?<lastName>(.*?)</lastName>", xml, re.S)]
        amt = lambda k: float(g[k]) if g[k] and g[k].replace(".", "").isdigit() else None  # noqa: E731  ("Indefinite" -> None)
        conn.execute("""INSERT OR REPLACE INTO funding_events (startup_id, event_date, source_name, event_type, amount, currency, investor_count, details, source_url)
                        VALUES (?,?, 'sec_form_d', 'form_d', ?, 'USD', ?, ?, ?)""",
                     (sid, first_sale.group(1) if first_sale else filed, amt("totalAmountSold"),
                      int(g["totalNumberAlreadyInvested"]) if (g["totalNumberAlreadyInvested"] or "").isdigit() else None,
                      json.dumps({"form": form, "filed_on": filed, "accession": acc, "offering": amt("totalOfferingAmount"),
                                  "is_amendment": g["isAmendment"], "industry": g["industryGroupType"], "related_persons": persons}),
                      f"https://www.sec.gov/Archives/edgar/data/{cik}/{acc.replace('-', '')}/"))
        for name in persons:
            conn.execute("INSERT INTO people (name) SELECT ? WHERE NOT EXISTS (SELECT 1 FROM people WHERE name=? AND ch_officer_id IS NULL)", (name, name))
            pid = conn.execute("SELECT id FROM people WHERE name=? AND ch_officer_id IS NULL", (name,)).fetchone()[0]
            conn.execute("INSERT OR IGNORE INTO startup_people (startup_id, person_id, role, source_name) VALUES (?,?, 'form_d_related_person', 'sec_form_d_document')", (sid, pid))
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
ITEM_W = {"sector": 2.0, "industry": 2.0, "yc": 1.5, "sic": 1.5, "impact": 1.5, "kw": 1.0}


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

        # founders
        people = conn.execute("""SELECT sp.*, p.name FROM startup_people sp JOIN people p ON p.id=sp.person_id
                                 WHERE sp.startup_id=? AND sp.source_name='uk_companies_house_company'""", (sid,)).fetchall()
        if people:
            reg = conn.execute("SELECT details FROM startup_external_ids WHERE startup_id=? AND id_type='company_number'", (sid,)).fetchone()
            created = parse_date(json.loads(reg["details"] or "{}").get("date_of_creation")) if reg else None
            founders = [p for p in people if p["is_founder"]]
            put("founder_count", len(founders), evidence=[p["name"] for p in founders])
            serial, prior_total, prior_failed, detail = 0, 0, 0, {}
            for p in founders:
                prior = [v for v in conn.execute("SELECT * FROM person_ventures WHERE person_id=?", (p["person_id"],))
                         if created and parse_date(v["appointed_on"]) and parse_date(v["appointed_on"]) < created]
                if prior:
                    serial += 1
                prior_total += len(prior)
                failed = [v for v in prior if (v["company_status"] or "") in ("dissolved", "liquidation", "administration", "receivership", "insolvency-proceedings")]
                prior_failed += len(failed)
                detail[p["name"]] = [f"{v['company_name']} ({v['company_status']}, from {v['appointed_on']})" for v in prior]
            put("serial_founder_count", serial, evidence=detail)
            put("prior_ventures_total", prior_total, evidence=detail)
            put("prior_ventures_failed", prior_failed)
            other = {p["name"]: [f"{v['company_name']} ({v['company_status']}, from {v['appointed_on']})"
                                 for v in conn.execute("SELECT * FROM person_ventures WHERE person_id=?", (p["person_id"],))] for p in founders}
            put("founder_other_ventures", sum(len(v) for v in other.values()), evidence=other)
            if founders:
                put("founder_retention", round(sum(1 for p in founders if not p["resigned_on"]) / len(founders), 3))
            put("officer_churn", round(sum(1 for p in people if p["resigned_on"]) / len(people), 3))

        # momentum
        hc = conn.execute("SELECT value, source_name, observed_on FROM startup_signals WHERE startup_id=? AND unit='employees' ORDER BY observed_on DESC, source_name='people_data_labs' DESC LIMIT 1", (sid,)).fetchone()
        if hc:
            put("headcount", hc["value"], evidence={"source": hc["source_name"], "observed_on": hc["observed_on"]})
        jobs = conn.execute("SELECT COUNT(*) FROM startup_signals WHERE startup_id=? AND signal_type='job'", (sid,)).fetchone()[0]
        if conn.execute("SELECT 1 FROM raw_fetches WHERE startup_id=? AND source_name='serpapi_google_jobs' AND status='ok'", (sid,)).fetchone():
            put("open_roles", jobs)
        news = conn.execute("SELECT COUNT(*) FROM startup_signals WHERE startup_id=? AND signal_type='news' AND observed_on>=?", (sid, cutoff.isoformat())).fetchone()[0]
        put("news_mentions_12m", news)
        pat = conn.execute("SELECT COUNT(*), SUM(json_extract(details,'$.grant_date') IS NOT NULL) FROM startup_signals WHERE startup_id=? AND signal_type='patent'", (sid,)).fetchone()
        if conn.execute("SELECT 1 FROM raw_fetches WHERE startup_id=? AND source_name LIKE '%patents%' AND status='ok'", (sid,)).fetchone():
            put("patent_count", pat[0])
            put("patents_granted", pat[1] or 0)

        # age, risk, integrity
        reg = conn.execute("SELECT details FROM startup_external_ids WHERE startup_id=? AND id_type IN ('company_number','lei') ORDER BY id_type='company_number' DESC LIMIT 1", (sid,)).fetchone()
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
            distress = int(insolv > 0 or (status or "").lower() in ("administration", "liquidation", "receivership", "insolvency-proceedings", "dissolved") or no_officers)
            put("distress_flag", distress, evidence={"insolvency_cases": insolv, "status": status, "no_active_officers": no_officers})
        years = {str(st["founded_year"])} if st["founded_year"] else set()
        years |= {r[0] for r in conn.execute("SELECT value FROM field_suggestions WHERE startup_id=? AND field='founded_year' AND status!='rejected'", (sid,))}
        if years:
            put("founded_year_conflicts", len(years), evidence=sorted(years))

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
