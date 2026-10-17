"""Read access to features, funding, people, investors, grants, patents and BlueInvest leads in the unified database.

Features and peers are in the latest assessment with features (Modules/DataAPIs/features.py, engine startupgo-pipeline);
everything else is facts in the Agent's format (sections A-J, Api) about startup, person, investor and candidate entities.
"""

import json
import re
import sqlite3
from typing import Any

from .schemas import (
    BlueInvestProfile,
    EuGrant,
    ExternalPeer,
    FeatureDefinition,
    FeatureValue,
    FundingEvent,
    InvestorLink,
    Patent,
    Peer,
    Person,
    StartupFeatures,
    Venture,
)

EVENT_TYPES = {"funding_rounds": "announced_round", "analyst": "announced_round", "agent": "announced_round", "uk_sh01": "priced_round",
               "sec_form_d": "form_d", "cordis_projects": "eu_grant"}  # by source; other grants are "grant"
DEV_STAGE_TRL = {"concept": 2, "lab_proof": 3, "prototype_lab": 4, "prototype_relevant_env": 6, "demo_operational_env": 7,
                 "qualified_system": 8, "commercial_operation": 9}  # when the evidence doesn't give the TRL


def _startup(conn: sqlite3.Connection, slug: str) -> sqlite3.Row | None:
    return conn.execute("SELECT * FROM entities WHERE kind = 'startup' AND slug = ?", (slug,)).fetchone()


def _json(s: str | None) -> Any:
    return json.loads(s) if s else None


def _facts(conn: sqlite3.Connection, entity_id: int, *fields: str, current: bool = True) -> list[sqlite3.Row]:
    marks = ", ".join("?" * len(fields))
    sql = f"SELECT * FROM facts WHERE entity_id = ? AND field IN ({marks})" + (" AND is_current = 1" if current else "")
    return conn.execute(sql + " ORDER BY observed_on, id", (entity_id, *fields)).fetchall()


# --- features ----------------------------------------------------------------------------------


def catalog(conn: sqlite3.Connection) -> list[FeatureDefinition]:
    rows = conn.execute("SELECT * FROM feature_definitions ORDER BY feature_group, importance, name").fetchall()
    return [FeatureDefinition(**dict(r)) for r in rows]


def latest_as_of(conn: sqlite3.Connection) -> str | None:
    return conn.execute("SELECT MAX(assessed_at) FROM assessments WHERE features IS NOT NULL").fetchone()[0]


def _features(conn: sqlite3.Connection, entity_id: int, as_of: str | None) -> dict[str, dict]:
    row = conn.execute("SELECT features FROM assessments WHERE entity_id = ? AND assessed_at = ? AND features IS NOT NULL ORDER BY id DESC LIMIT 1",
                       (entity_id, as_of)).fetchone()
    return (_json(row["features"]) or {}) if row else {}


def startup_features(conn: sqlite3.Connection, slug: str, as_of: str | None = None) -> StartupFeatures | None:
    st = _startup(conn, slug)
    if st is None:
        return None
    as_of = as_of or latest_as_of(conn)
    feats = _features(conn, st["id"], as_of)
    definitions = conn.execute("SELECT * FROM feature_definitions ORDER BY feature_group, name").fetchall()
    return StartupFeatures(
        slug=slug,
        as_of=as_of if feats else None,
        features=[
            FeatureValue(name=d["name"], feature_group=d["feature_group"], value=feats[d["name"]].get("value"), text=feats[d["name"]].get("text"),
                         unit=d["unit"], importance=d["importance"], evidence=feats[d["name"]].get("evidence"))
            for d in definitions if d["name"] in feats
        ],
        missing=sorted(d["name"] for d in definitions if d["name"] not in feats),
    )


def feature_matrix(conn: sqlite3.Connection, as_of: str | None = None) -> tuple[list[str], list[dict]]:
    """One row per startup, one column per feature (numeric value, else text). Missing = None."""
    as_of = as_of or latest_as_of(conn)
    names = [r[0] for r in conn.execute("SELECT name FROM feature_definitions ORDER BY feature_group, name")]
    rows = []
    for st in conn.execute("SELECT id, slug, name FROM entities WHERE kind = 'startup' ORDER BY id").fetchall():
        feats = _features(conn, st["id"], as_of)
        vals = {n: (f.get("value") if f.get("value") is not None else f.get("text")) for n, f in feats.items()}
        rows.append({"slug": st["slug"], "name": st["name"], "as_of": as_of, **{n: vals.get(n) for n in names}})
    return names, rows


# --- funding, people, investors, peers -----------------------------------------------------------


def funding_events(conn: sqlite3.Connection, slug: str) -> list[FundingEvent] | None:
    st = _startup(conn, slug)
    if st is None:
        return None
    out = []
    for f in _facts(conn, st["id"], "equity_rounds", "grants", "total_raised"):
        v = _json(f["value"])
        if f["field"] == "total_raised":
            event_type, v = "aggregate", {"amount": v, "currency": "USD"}
        else:
            event_type = EVENT_TYPES.get(f["source_name"], "grant" if f["field"] == "grants" else "round")
            if f["field"] == "grants" and event_type == "announced_round":
                event_type = "grant"
        out.append(FundingEvent(event_date=f["observed_on"], source_name=f["source_name"], event_type=event_type,
                                round_label=v.get("round_type") or v.get("programme") or (v.get("stage") if v.get("stage") != "other" else None),
                                amount=v.get("amount"), currency=v.get("currency"), price_per_share=v.get("price_per_share"),
                                investor_count=v.get("investor_count"), source_url=f["source_url"], status=f["status"],
                                confidence=f["confidence"], details=v))
    return sorted(out, key=lambda e: (e.event_date is None, e.event_date or ""))


def people(conn: sqlite3.Connection, slug: str, founders_only: bool = False) -> list[Person] | None:
    """Founders (and with ``founders_only=False`` board members), each with their other companies."""
    st = _startup(conn, slug)
    if st is None:
        return None
    created = conn.execute("SELECT MIN(observed_on) FROM facts WHERE entity_id = ? AND field = 'founded_date' AND source_type = 'registry'",
                           (st["id"],)).fetchone()[0]
    out = []
    for f in _facts(conn, st["id"], "founders", *(() if founders_only else ("advisors_board",))):
        v = _json(f["value"])
        person = f["related_entity_id"]
        education = next((_json(e["value"]) for e in _facts(conn, person, "education")), None) if person else None
        ventures = [
            Venture(company_name=w["company"], company_number=w.get("company_number"), company_status=w.get("status"), role=w.get("role"),
                    appointed_on=w.get("from"), resigned_on=w.get("to"),
                    before_startup=(w["from"] < created) if (created and w.get("from")) else None)
            for w in (_json(r["value"]) for r in (_facts(conn, person, "venture") if person else []))
        ]
        out.append(Person(name=v["name"], role=v.get("role") or v.get("background") or "", is_founder=f["field"] == "founders",
                          appointed_on=f["observed_on"], active=v.get("active"), source_name=f["source_name"], education=education,
                          ventures=ventures))
    return out


def investors(conn: sqlite3.Connection, slug: str) -> list[InvestorLink] | None:
    st = _startup(conn, slug)
    if st is None:
        return None
    out = []
    for f in _facts(conn, st["id"], "investor"):
        v = _json(f["value"])
        profile: dict = next((_json(p["value"]) for p in _facts(conn, f["related_entity_id"], "investor_profile")), {}) if f["related_entity_id"] else {}
        out.append(InvestorLink(name=v["name"], kind=profile.get("kind"), tier_score=profile.get("tier_score"), role=v["role"],
                                rounds=v.get("rounds") or 0, first_seen=v.get("first_seen")))
    return sorted(out, key=lambda i: (i.role != "lead", -(i.tier_score or 0)))


def _peers(conn: sqlite3.Connection, entity_id: int, source: str) -> list[dict]:
    row = conn.execute("SELECT peers FROM assessments WHERE entity_id = ? AND peers IS NOT NULL ORDER BY assessed_at DESC, id DESC LIMIT 1",
                       (entity_id,)).fetchone()
    peers = _json(row["peers"]) if row else []
    return sorted((p for p in peers if p.get("source") == source), key=lambda p: -p["similarity"])


def peers(conn: sqlite3.Connection, slug: str, limit: int = 5) -> list[Peer] | None:
    st = _startup(conn, slug)
    if st is None:
        return None
    out = []
    for p in _peers(conn, st["id"], "startupgo")[:limit]:
        other = conn.execute("SELECT slug, sector FROM entities WHERE kind = 'startup' AND name = ?", (p["name"],)).fetchone()
        out.append(Peer(slug=other["slug"] if other else None, name=p["name"], sector=other["sector"] if other else None, similarity=p["similarity"]))
    return out


# --- EU grants and patents ---------------------------------------------------------------------


def grants(conn: sqlite3.Connection, slug: str) -> list[EuGrant] | None:
    """EU-funded projects (CORDIS) the startup takes part in, with its own EU contribution and role."""
    st = _startup(conn, slug)
    if st is None:
        return None
    return [
        EuGrant(project_id=v["project_id"], programme=v.get("programme"), role=v.get("role"), ec_contribution=v.get("amount"),
                currency=v.get("currency"), start_date=f["observed_on"], is_eic=bool(v.get("eic")), is_mission_ocean=bool(v.get("mission_ocean")),
                url=f["source_url"])
        for f in _facts(conn, st["id"], "grants")
        if f["source_name"] == "cordis_projects" and (v := _json(f["value"])).get("project_id")
    ]


def patents(conn: sqlite3.Connection, slug: str) -> list[Patent] | None:
    st = _startup(conn, slug)
    if st is None:
        return None
    return [
        Patent(publication_number=v["number"], title=v.get("title") or "", url=f["source_url"], priority_date=f["observed_on"],
               legal_status=v.get("legal_status"), granted=v.get("granted"), ocean_groups=v.get("ocean_groups") or [])
        for f in _facts(conn, st["id"], "patents")
        if (v := _json(f["value"])).get("number")
    ]


# --- BlueInvest pipeline -------------------------------------------------------------------------


def _blueinvest_profile(conn: sqlite3.Connection, e: sqlite3.Row) -> BlueInvestProfile:
    """A BlueInvest lead (candidate entity) or a startup matched to one: TRL from its self-reported dev stage."""
    stage = next((f for f in _facts(conn, e["id"], "dev_stage") if f["source_name"] == "blueinvest_profile"), None)
    trl = None
    if stage:
        said = re.search(r"TRL\s*(\d)", stage["evidence"] or "")
        trl = int(said.group(1)) if said else DEV_STAGE_TRL.get(_json(stage["value"]))
    raise_ = next((f for f in _facts(conn, e["id"], "current_raise") if f["source_name"] == "blueinvest_profile"), None)
    summary = next((_json(f["value"]) for f in _facts(conn, e["id"], "blueinvest_summary")), None)
    candidate = e["kind"] == "candidate"
    source = stage or raise_
    return BlueInvestProfile(
        other_id=int(e["blueinvest_id"]), name=e["tagline"] if candidate and e["tagline"] else e["name"],
        summary=e["description"] if candidate else summary, trl=trl, sector=e["sector"], company=e["name"], country=e["country"],
        funding_sought_eur=(_json(raise_["value"]) or {}).get("amount") if raise_ else None, website=e["website"],
        matched_slug=None if candidate else e["slug"],
        url=source["source_url"] if source else None,
    )


def blueinvest(conn: sqlite3.Connection, q: str | None = None, sector: str | None = None, min_trl: int | None = None,
               matched_only: bool = False, limit: int = 50, offset: int = 0) -> list[BlueInvestProfile]:
    sql = "SELECT * FROM entities WHERE blueinvest_id IS NOT NULL AND kind IN ('startup', 'candidate')"
    args: list = []
    if q:
        sql += " AND (name LIKE ? OR tagline LIKE ? OR description LIKE ?)"
        args += [f"%{q}%"] * 3
    if sector:
        sql += " AND sector = ?"
        args.append(sector)
    if matched_only:
        sql += " AND kind = 'startup'"
    found = [_blueinvest_profile(conn, e) for e in conn.execute(sql, args).fetchall()]
    found = [p for p in found if min_trl is None or (p.trl is not None and p.trl >= min_trl)]
    found.sort(key=lambda p: (-(p.trl or 0), p.name))
    return found[offset:offset + limit]


def external_peers(conn: sqlite3.Connection, slug: str, limit: int = 10) -> list[ExternalPeer] | None:
    """Most similar BlueInvest projects; each is linked to its lead when the project name finds one."""
    st = _startup(conn, slug)
    if st is None:
        return None
    out = []
    for p in _peers(conn, st["id"], "blueinvest")[:limit]:
        lead = conn.execute("SELECT blueinvest_id, website FROM entities WHERE kind = 'candidate' AND tagline = ?", (p["name"][:200],)).fetchone()
        out.append(ExternalPeer(source="blueinvest", external_id=lead["blueinvest_id"] if lead else None, name=p["name"],
                                similarity=p["similarity"], trl=p.get("trl"), sector=p.get("sector"), website=lead["website"] if lead else None))
    return out
