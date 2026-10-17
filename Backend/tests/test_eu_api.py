"""EU grants, patents and the BlueInvest pipeline: read from the unified database's facts and candidate entities."""

import sqlite3

import pytest

from app.db import db_path


@pytest.mark.parametrize("ep", ["grants", "patents", "peers/blueinvest"])
def test_unknown_startup_is_404(client, ep):
    assert client.get(f"/api/startups/nope/{ep}").status_code == 404


def test_the_unified_database_has_them_for_seed_startups(client):
    assert any(g["programme"] for g in client.get("/api/startups/notpla/grants").json())
    assert client.get("/api/startups/notpla/patents").json()[0]["publication_number"]
    leads = [p for offset in (0, 500) for p in client.get("/api/discovery/blueinvest", params={"limit": 500, "offset": offset}).json()]
    assert len(leads) > 600 and any(p["matched_slug"] for p in leads)  # candidates, and startups matched to a lead
    assert client.get("/api/startups/notpla/peers/blueinvest").json()


@pytest.fixture()
def seeded(client):
    conn = sqlite3.connect(db_path())
    conn.executescript("""
        INSERT INTO entities (id, key, kind, slug, name, tagline, description, sector, country, website, blueinvest_id, pipeline_stage) VALUES
          (900, 'startup:testco', 'startup', 'testco', 'TestCo', 'Packaging', '', 'Testing', 'UK', NULL, '807', 'sourced'),
          (901, 'blueinvest:9001', 'candidate', NULL, 'Other Co', 'Oyster reefs project', 'Restoring oyster reefs', 'Testing', 'FR',
           'https://other.example', '9001', 'candidate');
        INSERT INTO facts (entity_id, section, field, value, evidence, source_url, source_type, source_name, status, confidence, observed_on) VALUES
          (900, 'G', 'grants', '{"funder": "European Commission", "programme": "H2020 UCUP", "amount": 50000, "currency": "EUR", "year": 2017,
             "role": "coordinator", "project_id": "760405", "eic": true, "mission_ocean": false}', 'UCUP', 'https://cordis.europa.eu/project/id/760405',
             'eu_projects', 'cordis_projects', 'verified', 0.9, '2017-12-01'),
          (900, 'C', 'patents', '{"number": "EP3601061B1", "title": "Method of encapsulating liquid products", "year": 2017, "legal_status": "Active",
             "granted": "2023-03-08", "ocean_groups": ["marine-bio"]}', 'EP3601061B1', 'https://patents.google.com/patent/EP3601061B1', 'patent',
             'serpapi_google_patents', 'verified', 0.9, '2017-03-22'),
          (900, 'C', 'dev_stage', '"commercial_operation"', 'Self-reported TRL 9 - Actual system proven (BlueInvest)', 'https://example/807',
             'website', 'blueinvest_profile', 'claimed', 0.7, NULL),
          (900, 'Api', 'blueinvest_summary', '"Seaweed biorefinery"', 'Seaweed biorefinery', 'https://example/807', 'website', 'blueinvest_profile',
             'claimed', 0.7, NULL),
          (901, 'C', 'dev_stage', '"prototype_relevant_env"', 'TRL 5 - Technology validated', 'https://example/9001', 'website', 'blueinvest_profile',
             'claimed', 0.7, NULL),
          (901, 'G', 'current_raise', '{"amount": 250000, "currency": "EUR", "stage": null, "open": true}', 'seeking', 'https://example/9001',
             'website', 'blueinvest_profile', 'claimed', 0.6, NULL);
        INSERT INTO assessments (entity_id, assessed_at, engine, peers) VALUES
          (900, '2027-01-01', 'startupgo-pipeline', '[{"name": "Oyster reefs project", "similarity": 0.22, "trl": 5, "sector": "Testing", "source": "blueinvest"}]');
    """)
    conn.commit()
    conn.close()
    return client


def test_grants(seeded):
    [g] = seeded.get("/api/startups/testco/grants").json()
    assert (g["project_id"], g["programme"], g["is_eic"], g["ec_contribution"], g["start_date"]) == ("760405", "H2020 UCUP", True, 50000, "2017-12-01")


def test_patents(seeded):
    [p] = seeded.get("/api/startups/testco/patents").json()
    assert (p["publication_number"], p["ocean_groups"], p["legal_status"], p["priority_date"]) == ("EP3601061B1", ["marine-bio"], "Active", "2017-03-22")


def test_discovery_filters(seeded):
    found = seeded.get("/api/discovery/blueinvest", params={"sector": "Testing"}).json()
    assert [(p["name"], p["trl"], p["matched_slug"]) for p in found] == [("TestCo", 9, "testco"), ("Oyster reefs project", 5, None)]
    assert found[0]["summary"] == "Seaweed biorefinery" and found[1]["funding_sought_eur"] == 250000 and found[1]["company"] == "Other Co"
    assert [p["name"] for p in seeded.get("/api/discovery/blueinvest", params={"sector": "Testing", "min_trl": 8}).json()] == ["TestCo"]
    assert [p["name"] for p in seeded.get("/api/discovery/blueinvest", params={"sector": "Testing", "matched_only": True}).json()] == ["TestCo"]
    assert [p["name"] for p in seeded.get("/api/discovery/blueinvest", params={"q": "oyster reefs project"}).json()] == ["Oyster reefs project"]


def test_blueinvest_peers(seeded):
    [p] = seeded.get("/api/startups/testco/peers/blueinvest").json()
    assert (p["name"], p["external_id"], p["trl"], p["website"]) == ("Oyster reefs project", "9001", 5, "https://other.example")
