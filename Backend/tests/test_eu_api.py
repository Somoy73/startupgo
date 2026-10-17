import sqlite3

import pytest

from app.db import db_path


@pytest.mark.parametrize("ep", ["grants", "patents"])
def test_unknown_startup_is_404(client, ep):
    assert client.get(f"/api/startups/nope/{ep}").status_code == 404


@pytest.mark.parametrize("ep", ["grants", "patents"])
def test_fresh_db_empty(client, ep):
    assert client.get(f"/api/startups/notpla/{ep}").json() == []


def test_discovery_empty_on_fresh_db(client):
    assert client.get("/api/discovery/blueinvest").json() == []


@pytest.fixture()
def seeded(client):
    conn = sqlite3.connect(db_path())
    conn.executescript("""
        INSERT INTO eu_grants (startup_id, project_id, acronym, framework, topic_codes, legal_basis, role, ec_contribution, sme,
                               partners, start_date, status, is_eic, is_mission_ocean, categories, url)
          VALUES (1,'760405','UCUP','H2020','["SMEInst-11-2016-2017"]','["H2020-EU.2.3.1."]','coordinator',50000,1,0,'2017-12-01','CLOSED',1,0,
                  '["sustainable economy"]','https://cordis.europa.eu/project/id/760405');
        INSERT INTO startup_signals (startup_id, source_name, signal_type, title, url, observed_on, details, match_confidence)
          VALUES (1,'serpapi_google_patents','patent','EP3601061B1: Method of encapsulating liquid products','https://patents.google.com/patent/EP3601061B1',
                  '2017-03-22','{"legal_status": "Active", "ocean_groups": ["marine-bio"]}','high');
        INSERT INTO patent_classes VALUES (1,'EP3601061B1','B65D65/46',NULL), (1,'EP3601061B1','A61K8/9706','marine-bio');
        INSERT INTO blueinvest_profiles (other_id, name, summary, trl, sector, startup_id, url)
          VALUES (807,'Oceanium','Seaweed biorefinery',9,'Blue biotechnology',5,'https://example/807'),
                 (1,'Other Co','Oyster reefs',5,'Coastal and environmental protection and regeneration',NULL,'https://example/1');
    """)
    conn.commit()
    conn.close()
    return client


def test_grants(seeded):
    [g] = seeded.get("/api/startups/notpla/grants").json()
    assert g["acronym"] == "UCUP" and g["is_eic"] is True and g["ec_contribution"] == 50000
    assert g["topic_codes"] == ["SMEInst-11-2016-2017"]


def test_patents_with_classes(seeded):
    [p] = seeded.get("/api/startups/notpla/patents").json()
    assert p["publication_number"] == "EP3601061B1" and p["ocean_groups"] == ["marine-bio"]
    assert p["cpc_codes"] == ["A61K8/9706", "B65D65/46"] and p["legal_status"] == "Active"


def test_discovery_filters(seeded):
    assert [p["name"] for p in seeded.get("/api/discovery/blueinvest").json()] == ["Oceanium", "Other Co"]
    assert [p["name"] for p in seeded.get("/api/discovery/blueinvest?min_trl=8").json()] == ["Oceanium"]
    assert seeded.get("/api/discovery/blueinvest?matched_only=true").json()[0]["matched_slug"] == "oceanium"
    assert [p["name"] for p in seeded.get("/api/discovery/blueinvest?q=oyster").json()] == ["Other Co"]


def test_blueinvest_peers(client):
    assert client.get("/api/startups/nope/peers/blueinvest").status_code == 404
    assert client.get("/api/startups/notpla/peers/blueinvest").json() == []
    conn = sqlite3.connect(db_path())
    conn.execute("""INSERT INTO startup_external_peers VALUES (1,'blueinvest','42','noriware AG',0.22,'["seaweed","packaging"]',6,'Blue biotechnology','https://x/42')""")
    conn.commit()
    conn.close()
    [p] = client.get("/api/startups/notpla/peers/blueinvest").json()
    assert p["name"] == "noriware AG" and p["shared_tags"] == ["seaweed", "packaging"] and p["trl"] == 6


def test_founder_education_and_pdl_roles(client):
    conn = sqlite3.connect(db_path())
    conn.executescript("""
        INSERT INTO people (id, name, pdl_id, education) VALUES (7,'Daniel Hooft','pdl-1','[{"school": "TU Delft", "degrees": ["master of science"]}]');
        INSERT INTO startup_people VALUES (7,7,'chief executive officer',1,'2020-01',NULL,'people_data_labs');
        INSERT INTO person_ventures VALUES (7,'pdl:x','Stimblue+',NULL,'chief executive officer','2020-01',NULL,'people_data_labs');
    """)
    conn.commit()
    conn.close()
    [p] = client.get("/api/startups/kelp-blue/founders").json()
    assert p["source_name"] == "people_data_labs" and p["education"][0]["degrees"] == ["master of science"]
    assert p["ventures"][0]["company_name"] == "Stimblue+"
