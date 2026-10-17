"""Judge-approved entries into the StartupGo database: KTH levels, Navigator KPIs, startups, rounds, sources."""

import sqlite3
from pathlib import Path

import pytest

from startup_agent.database import StartupDatabase, domain
from startup_agent.errors import AgentError
from startup_agent.graph import build_agent_graph
from startup_agent.kth import score_crl, score_frl, score_iprl, score_tmrl
from startup_agent.navigator import kpi_codes, ocean_kpis

from .helpers import fact

DB_DIR = Path(__file__).resolve().parents[3] / "DB"


def make_db(path: Path) -> StartupDatabase:
    conn = sqlite3.connect(path)
    conn.executescript((DB_DIR / "schema.sql").read_text())
    conn.executescript((DB_DIR / "seed.sql").read_text())
    conn.close()
    return StartupDatabase(path)


def rows(path: Path, sql: str, *args):
    conn = sqlite3.connect(path)
    conn.row_factory = sqlite3.Row
    try:
        return conn.execute(sql, args).fetchall()
    finally:
        conn.close()


@pytest.fixture
def entry(agent):
    agent, _ = agent
    result = build_agent_graph(agent).invoke({"mode": "both", "name": "Acme Ocean", "website": "https://acme.fi"})
    return result["evaluated"][0]


# --- KTH levels ----------------------------------------------------------------------------


def test_kth_levels_follow_the_facts():
    assert score_crl({}).level is None
    assert score_crl({"customer_validation": fact("customer_validation", "paid_pilot")}).level == 6
    assert score_crl({"paying_customers": fact("paying_customers", {"count": 12, "names": []})}).level == 8

    assert score_iprl({"patents": [fact("patents", {"number": "WO2024123456A1", "title": "x", "year": 2024})]}).level == 5
    two_offices = [fact("patents", {"number": n, "title": "x", "year": 2024}) for n in ("FI 130000 A", "EP 4000000 A1")]
    assert score_iprl({"patents": two_offices}).level == 7
    assert score_iprl({"patents": [fact("patents", {"number": "EP 3 456 789 B1", "title": "x", "year": 2020})]}).level == 8

    founders = [fact("founders", {"name": "A", "role": "CEO", "technical": False}), fact("founders", {"name": "B", "role": "CTO", "technical": True})]
    assert score_tmrl({"founders": founders[:1]}).level == 2
    assert score_tmrl({"founders": founders, "key_roles_missing": fact("key_roles_missing", ["commercial lead"])}).level == 5
    full = {"founders": founders, "key_roles_missing": fact("key_roles_missing", []), "advisors_board": [fact("advisors_board", {"name": "C"})],
            "team_size": fact("team_size", 12)}
    assert score_tmrl(full).level == 7

    assert score_frl({"stage": fact("stage", "seed")}).level == 6
    assert score_frl({"grants": [fact("grants", {"funder": "EIC"})], "current_raise": fact("current_raise", {"open": True})}).level == 5


# --- Ocean Impact Navigator ------------------------------------------------------------------


def test_navigator_maps_impact_facts_to_kpis_with_evidence_levels():
    assert kpi_codes("Removes microplastics from wastewater") == ["B1", "B4"]
    assert set(kpi_codes("cuts CO2 and NOx emissions from ships")) == {"D1", "D4"}
    facts = {
        "impact_claim": fact("impact_claim", "Replaces single-use plastic packaging"),
        "impact_measured": [fact("impact_measured", {"metric": "plastic avoided", "value": "120 t", "period": "2025"}),
                            fact("impact_measured", {"metric": "CO2 avoided", "value": "40 t", "period": "2025"})],
        "impact_verified_by": fact("impact_verified_by", "DNV"),
    }
    found = {k.code: k.level for k in ocean_kpis(facts)}
    assert found == {"B2": 4, "D1": 4}  # measured and verified beats the plain claim
    assert ocean_kpis({"impact_claim": fact("impact_claim", "Restores seagrass meadows", status="verified")})[0].level == 2


# --- storing -----------------------------------------------------------------------------------


def test_new_startup_is_created_with_a_full_assessment(tmp_path, entry):
    db = make_db(tmp_path / "db.sqlite")
    stored = db.save(entry)
    assert (stored.slug, stored.created, stored.skipped) == ("acme-ocean", True, "")

    (startup,) = rows(db.path, "SELECT * FROM startups WHERE slug = 'acme-ocean'")
    assert (startup["website"], startup["country"], startup["tagline"]) == ("https://acme.fi/", "Finland", "Sediment sensors for ports")
    (assessment,) = rows(db.path, "SELECT * FROM readiness_assessments WHERE startup_id = ?", startup["id"])
    assert (assessment["assessor"], assessment["trl"], assessment["tmrl"]) == ("StartupGo agent", 6, 5)
    assert assessment["iprl"] == 1 and "no evidence for" in assessment["rationale"] and "IPRL" in assessment["rationale"]
    assert {r["url"] for r in rows(db.path, "SELECT url FROM sources WHERE startup_id = ?", startup["id"])} >= {"https://acme.fi/technology"}
    (link,) = rows(db.path, "SELECT * FROM agent_entries")
    assert (link["entry_id"], link["assessment_id"]) == ("acme-fi", assessment["id"])


def test_saving_again_is_a_no_op_and_existing_startups_are_matched_by_domain(tmp_path, entry):
    db = make_db(tmp_path / "db.sqlite")
    conn = sqlite3.connect(db.path)
    conn.execute("INSERT INTO startups (slug, name, tagline, description, sector, country, stage, website) "
                 "VALUES ('acme', 'Acme', 'Analyst tagline', '', 'Ocean data', 'Unknown', 'seed', 'http://www.acme.fi/')")
    conn.commit()
    conn.close()

    first = db.save(entry)
    assert (first.slug, first.created) == ("acme", False)
    (startup,) = rows(db.path, "SELECT * FROM startups WHERE slug = 'acme'")
    assert startup["tagline"] == "Analyst tagline"  # analyst data is kept
    assert startup["country"] == "Finland" and startup["description"]  # blanks are filled in
    assert db.save(entry).skipped == "entry already stored"
    assert len(rows(db.path, "SELECT * FROM readiness_assessments WHERE startup_id = ?", startup["id"])) == 1


def test_only_accepted_entries_are_stored(tmp_path, entry):
    db = make_db(tmp_path / "db.sqlite")
    stored = db.save({**entry, "review": {**entry["review"], "status": "redo_requested"}})
    assert stored.skipped == "judge status redo_requested"
    assert not rows(db.path, "SELECT * FROM startups WHERE website = 'https://acme.fi'")


def test_kpi_evidence_is_raised_but_never_lowered(tmp_path, entry):
    db = make_db(tmp_path / "db.sqlite")  # seed: notpla B2 at 2 (evidenced), D1 at 1 (claimed)
    facts = entry["sections"]["E"]["facts"]
    facts["impact_claim"] = fact("impact_claim", "Replaces plastic packaging").to_dict()  # B2 claimed: 1 < 2
    facts["impact_measured"] = [fact("impact_measured", {"metric": "CO2 avoided", "value": "40 t", "period": "2025"}).to_dict()]  # D1 measured: 3
    assert db.save(entry, slug="notpla").kpis == ["B2", "D1"]
    levels = {r["kpi_code"]: r["evidence_level"] for r in rows(
        db.path, "SELECT kpi_code, evidence_level FROM startup_ocean_kpis k JOIN startups s ON s.id = k.startup_id WHERE s.slug = 'notpla'")}
    assert levels == {"B2": 2, "D1": 3}


def test_pending_lists_startups_without_a_recent_entry(tmp_path, entry):
    db = make_db(tmp_path / "db.sqlite")
    pending = db.pending(limit=20, max_age_days=30)
    assert "notpla" in {c.slug for c in pending} and "seaforester" not in {c.slug for c in pending}  # no website
    db.save(entry, slug="notpla")
    assert "notpla" not in {c.slug for c in db.pending(limit=20, max_age_days=30)}
    assert [c.slug for c in db.pending(limit=20, max_age_days=30, slugs=("notpla",))] == ["notpla"]
    assert db.known_domains()["notpla.com"] == "notpla"


def test_missing_tables_are_reported(tmp_path):
    sqlite3.connect(tmp_path / "old.db").close()
    with pytest.raises(AgentError, match="agent_entries"):
        StartupDatabase(tmp_path / "old.db").pending(limit=1, max_age_days=1)
    assert domain("HTTPS://www.Acme.fi:8080/x") == "acme.fi"
