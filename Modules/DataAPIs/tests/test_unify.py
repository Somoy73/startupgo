"""The 3-table model: build from main's seed data, rebuild stability, and read equivalence of the compatibility views."""
import sqlite3
import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
import ingest  # noqa: E402
import unify  # noqa: E402


@pytest.fixture()
def db(tmp_path, monkeypatch):
    path = tmp_path / "startupgo.db"
    monkeypatch.setenv("STARTUPGO_DB", str(path))
    monkeypatch.setenv("STARTUPGO_SNAPSHOT_DB", str(path))  # build from schema.sql + seed.sql
    conn = ingest.open_db()
    unify.build(conn)
    return conn, path


def test_startups_become_entities_with_their_ids(db):
    conn, _ = db
    rows = conn.execute("SELECT e.id, e.slug FROM entities e WHERE kind='startup' ORDER BY id").fetchall()
    assert [tuple(r) for r in rows] == [tuple(r) for r in conn.execute("SELECT id, slug FROM startups ORDER BY id")]


def test_seed_rounds_and_kpis_become_agent_facts(db):
    conn, _ = db
    q = lambda sql: conn.execute(sql).fetchone()[0]  # noqa: E731
    assert q("SELECT COUNT(*) FROM facts WHERE source_name='funding_rounds' AND field IN ('equity_rounds','grants')") == q("SELECT COUNT(*) FROM funding_rounds")
    assert q("SELECT COUNT(*) FROM facts WHERE field='navigator_kpi'") == q("SELECT COUNT(*) FROM startup_ocean_kpis")
    stage = conn.execute("SELECT json_extract(value,'$.stage') FROM facts WHERE field='equity_rounds' AND entity_id=4").fetchone()[0]
    assert stage == "seed"  # Agent vocabulary (ROUND_STAGES)
    assert q("SELECT COUNT(*) FROM assessments WHERE engine='seed-estimate'") == 8


def test_rebuild_is_stable_and_keeps_agent_output(db):
    conn, _ = db
    ids = dict(conn.execute("SELECT key, id FROM entities").fetchall())
    conn.execute("INSERT INTO facts (entity_id, section, field, value, source_type, source_name, status, confidence) "
                 "VALUES (1, 'D', 'business_model', '\"product_sale\"', 'website', 'agent', 'claimed', 0.7)")
    conn.execute("INSERT INTO assessments (entity_id, assessed_at, engine, trl, oir) VALUES (1, '2026-10-17T10:00', 'agent', 8, 2)")
    conn.commit()
    n_facts = conn.execute("SELECT COUNT(*) FROM facts").fetchone()[0]
    unify.build(conn)
    assert dict(conn.execute("SELECT key, id FROM entities").fetchall()) == ids
    assert conn.execute("SELECT COUNT(*) FROM facts").fetchone()[0] == n_facts  # no duplicates
    assert conn.execute("SELECT COUNT(*) FROM facts WHERE source_name='agent'").fetchone()[0] == 1
    assert conn.execute("SELECT COUNT(*) FROM assessments WHERE engine='agent'").fetchone()[0] == 1


def rows(conn, sql):
    return sorted(tuple(r) for r in conn.execute(sql).fetchall())


def test_three_table_copy_reads_like_mains_tables(db, tmp_path):
    conn, path = db
    out = unify.preview(path, tmp_path / "three.db")
    new = sqlite3.connect(out)
    tables = {r[0] for r in new.execute("SELECT name FROM sqlite_master WHERE type='table'")}
    assert tables == {"entities", "facts", "assessments"}
    checks = {
        "startups": "SELECT id, slug, name, tagline, description, sector, country, city, founded_year, website, stage, pipeline_stage FROM startups",
        "readiness_assessments": "SELECT startup_id, assessed_on, assessor, confidence, crl, trl, brl, iprl, tmrl, frl, rationale FROM readiness_assessments",
        "startup_ocean_kpis": "SELECT startup_id, kpi_code, evidence_level, claim, source_url FROM startup_ocean_kpis",
        "funding_rounds": "SELECT startup_id, round_type, amount, currency, announced_on, lead_investors, notes, source_url FROM funding_rounds",
        "sources": "SELECT startup_id, title, url FROM sources",
        "readiness_levels": "SELECT * FROM readiness_levels",
        "ocean_kpis": "SELECT * FROM ocean_kpis",
        "ocean_impact_areas": "SELECT * FROM ocean_impact_areas",
        "readiness_dimensions": "SELECT * FROM readiness_dimensions",
    }
    for name, sql in checks.items():
        assert rows(conn, sql) == rows(new, sql), name


def test_unassessed_startups_are_hidden_from_mains_view(db, tmp_path):
    conn, path = db
    conn.execute("INSERT INTO startups (slug, name, tagline, description, sector, country, stage) "
                 "VALUES ('newco', 'NewCo', 't', 'd', 'Aquaculture', 'Finland', 'unknown')")
    conn.commit()
    unify.build(conn)
    assert conn.execute("SELECT COUNT(*) FROM entities WHERE slug='newco'").fetchone()[0] == 1
    new = sqlite3.connect(unify.preview(path, tmp_path / "three.db"))
    assert new.execute("SELECT COUNT(*) FROM startups WHERE slug='newco'").fetchone()[0] == 0  # no assessment yet


def test_schema_script_builds_the_3_table_database(db, tmp_path):
    conn, _ = db
    script = unify.unified_sql(conn)
    new = sqlite3.connect(tmp_path / "unified.db")
    new.executescript(script)
    new.executescript(script)  # applying it again changes nothing (the Backend does on every start)
    kinds = dict(new.execute("SELECT name, type FROM sqlite_master WHERE name NOT LIKE 'sqlite_%' AND type IN ('table', 'view')"))
    assert {n for n, t in kinds.items() if t == "table"} == {"entities", "facts", "assessments"}
    assert {*unify.COMPAT_VIEWS, *unify.REFERENCE_TABLES} <= {n for n, t in kinds.items() if t == "view"}
    assert new.execute("SELECT COUNT(*) FROM readiness_levels").fetchone()[0] == 54


def test_a_lead_the_agent_made_a_startup_stays_one(db):
    conn, _ = db
    conn.execute("INSERT INTO blueinvest_profiles (other_id, name, trl, sector, company, url) "
                 "VALUES (807, 'Kelp project', 6, 'Aquaculture', 'KelpCo', 'https://example/807')")
    unify.build(conn)
    conn.execute("UPDATE entities SET kind='startup', slug='kelpco', pipeline_stage='sourced' WHERE key='blueinvest:807'")
    eid = conn.execute("SELECT id FROM entities WHERE key='blueinvest:807'").fetchone()[0]
    conn.execute("INSERT INTO assessments (entity_id, assessed_at, engine, trl) VALUES (?, '2026-10-17 10:00:00', 'agent', 6)", (eid,))
    conn.commit()
    unify.build(conn)
    assert tuple(conn.execute("SELECT kind, slug FROM entities WHERE key='blueinvest:807'").fetchone()) == ("startup", "kelpco")
