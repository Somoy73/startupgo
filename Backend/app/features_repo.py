"""Read access to the success-prediction tables built by DataAPIs/features.py."""

import json
import sqlite3

from .schemas import FeatureDefinition, FeatureValue, FundingEvent, InvestorLink, Peer, Person, StartupFeatures, Venture


def _startup(conn: sqlite3.Connection, slug: str) -> sqlite3.Row | None:
    return conn.execute("SELECT * FROM startups WHERE slug = ?", (slug,)).fetchone()


def _json(s: str | None):
    return json.loads(s) if s else None


def catalog(conn: sqlite3.Connection) -> list[FeatureDefinition]:
    rows = conn.execute("SELECT * FROM feature_definitions ORDER BY feature_group, importance, name").fetchall()
    return [FeatureDefinition(**dict(r)) for r in rows]


def latest_as_of(conn: sqlite3.Connection) -> str | None:
    return conn.execute("SELECT MAX(as_of) FROM startup_features").fetchone()[0]


def startup_features(conn: sqlite3.Connection, slug: str, as_of: str | None = None) -> StartupFeatures | None:
    st = _startup(conn, slug)
    if st is None:
        return None
    as_of = as_of or latest_as_of(conn)
    rows = conn.execute(
        """SELECT d.name, d.feature_group, d.unit, d.importance, f.value_num, f.value_text, f.evidence
           FROM feature_definitions d JOIN startup_features f ON f.feature = d.name
           WHERE f.startup_id = ? AND f.as_of = ? ORDER BY d.feature_group, d.name""",
        (st["id"], as_of),
    ).fetchall()
    have = {r["name"] for r in rows}
    missing = [r[0] for r in conn.execute("SELECT name FROM feature_definitions ORDER BY name") if r[0] not in have]
    return StartupFeatures(
        slug=slug,
        as_of=as_of,
        features=[
            FeatureValue(name=r["name"], feature_group=r["feature_group"], value=r["value_num"], text=r["value_text"],
                         unit=r["unit"], importance=r["importance"], evidence=_json(r["evidence"]))
            for r in rows
        ],
        missing=missing,
    )


def feature_matrix(conn: sqlite3.Connection, as_of: str | None = None) -> tuple[list[str], list[dict]]:
    """One row per startup, one column per feature (numeric value, else text). Missing = None."""
    as_of = as_of or latest_as_of(conn)
    names = [r[0] for r in conn.execute("SELECT name FROM feature_definitions ORDER BY feature_group, name")]
    rows = []
    for st in conn.execute("SELECT id, slug, name FROM startups ORDER BY id").fetchall():
        vals = {r["feature"]: (r["value_num"] if r["value_num"] is not None else r["value_text"])
                for r in conn.execute("SELECT feature, value_num, value_text FROM startup_features WHERE startup_id=? AND as_of=?", (st["id"], as_of))}
        rows.append({"slug": st["slug"], "name": st["name"], "as_of": as_of, **{n: vals.get(n) for n in names}})
    return names, rows


def funding_events(conn: sqlite3.Connection, slug: str, include_nominal: bool = False) -> list[FundingEvent] | None:
    st = _startup(conn, slug)
    if st is None:
        return None
    sql = "SELECT * FROM funding_events WHERE startup_id = ?"
    if not include_nominal:
        sql += " AND event_type NOT IN ('nominal_allotment', 'allotment_unparsed')"
    rows = conn.execute(sql + " ORDER BY event_date, id", (st["id"],)).fetchall()
    return [FundingEvent(**{k: r[k] for k in FundingEvent.model_fields if k != "details"}, details=_json(r["details"])) for r in rows]


def people(conn: sqlite3.Connection, slug: str, founders_only: bool = False) -> list[Person] | None:
    st = _startup(conn, slug)
    if st is None:
        return None
    reg = conn.execute("SELECT details FROM startup_external_ids WHERE startup_id=? AND id_type='company_number'", (st["id"],)).fetchone()
    created = (_json(reg["details"]) or {}).get("date_of_creation") if reg else None
    sql = """SELECT sp.*, p.name, p.nationality FROM startup_people sp JOIN people p ON p.id = sp.person_id WHERE sp.startup_id = ?"""
    if founders_only:
        sql += " AND sp.is_founder = 1"
    out = []
    for r in conn.execute(sql + " ORDER BY sp.is_founder DESC, sp.appointed_on", (st["id"],)).fetchall():
        ventures = [
            Venture(company_name=v["company_name"], company_number=v["company_number"], company_status=v["company_status"], role=v["role"],
                    appointed_on=v["appointed_on"], resigned_on=v["resigned_on"],
                    before_startup=(v["appointed_on"] < created) if (created and v["appointed_on"]) else None)
            for v in conn.execute("SELECT * FROM person_ventures WHERE person_id = ? ORDER BY appointed_on", (r["person_id"],))
        ]
        out.append(Person(name=r["name"], role=r["role"], is_founder=bool(r["is_founder"]), appointed_on=r["appointed_on"],
                          resigned_on=r["resigned_on"], nationality=r["nationality"], source_name=r["source_name"], ventures=ventures))
    return out


def investors(conn: sqlite3.Connection, slug: str) -> list[InvestorLink] | None:
    st = _startup(conn, slug)
    if st is None:
        return None
    rows = conn.execute(
        """SELECT i.name, i.kind, i.tier_score, si.role, si.rounds, si.first_seen FROM startup_investors si
           JOIN investors i ON i.id = si.investor_id WHERE si.startup_id = ? ORDER BY si.role = 'lead' DESC, i.tier_score DESC""",
        (st["id"],),
    ).fetchall()
    return [InvestorLink(**dict(r)) for r in rows]


def peers(conn: sqlite3.Connection, slug: str, limit: int = 5) -> list[Peer] | None:
    st = _startup(conn, slug)
    if st is None:
        return None
    rows = conn.execute(
        """SELECT s.slug, s.name, s.sector, p.similarity, p.shared_tags FROM startup_peers p JOIN startups s ON s.id = p.peer_id
           WHERE p.startup_id = ? ORDER BY p.similarity DESC LIMIT ?""",
        (st["id"], limit),
    ).fetchall()
    return [Peer(slug=r["slug"], name=r["name"], sector=r["sector"], similarity=r["similarity"], shared_tags=_json(r["shared_tags"]) or []) for r in rows]
