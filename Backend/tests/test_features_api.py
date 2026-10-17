import sqlite3

import pytest

from app.db import db_path

ENDPOINTS = ["features", "rounds", "founders", "investors", "peers"]


@pytest.mark.parametrize("ep", ENDPOINTS)
def test_unknown_startup_is_404(client, ep):
    assert client.get(f"/api/startups/nope/{ep}").status_code == 404


@pytest.mark.parametrize("ep", ["rounds", "founders", "investors", "peers"])
def test_fresh_db_returns_empty_lists(client, ep):
    r = client.get(f"/api/startups/notpla/{ep}")
    assert r.status_code == 200
    assert r.json() == []


def test_fresh_db_features_all_missing(client):
    body = client.get("/api/startups/notpla/features").json()
    assert body["features"] == [] and body["as_of"] is None


@pytest.fixture()
def seeded(client):
    conn = sqlite3.connect(db_path())
    conn.executescript("""
        INSERT INTO feature_definitions VALUES
          ('total_raised_usd','rounds','Total raised','USD','high','paper','x'),
          ('no_round_24m','rounds','730-day rule','flag','high','paper','x'),
          ('lead_investors','investors','Leads',NULL,'high','user-list','x');
        INSERT INTO startup_features VALUES
          (1,'total_raised_usd','2026-10-17',48219216,NULL,'{"people_data_labs": 48219216}'),
          (1,'lead_investors','2026-10-17',NULL,'UB Forest','null');
        INSERT INTO funding_events (startup_id, event_date, source_name, event_type, amount, currency, share_class, shares_allotted,
                                    price_per_share, total_shares_after, implied_post_money, details)
          VALUES (1,'2021-09-24','uk_sh01','priced_allotment',10000001.62,'GBP','SERIES A PREFERRED',1887897,5.2969,7942043,42068207.57,'{}'),
                 (1,'2022-01-01','uk_sh01','nominal_allotment',1,'GBP','B ORDINARY',1000,0.000001,7943043,NULL,'{}');
        INSERT INTO people (id, name, ch_officer_id) VALUES (1,'PASLIER, Pierre-Yves','abc');
        INSERT INTO startup_people VALUES (1,1,'director',1,'2014-07-25',NULL,'uk_companies_house_company');
        INSERT INTO person_ventures VALUES (1,'09215060','GRAVITY SKETCH LIMITED','active','director','2014-09-22','2016-04-08','uk_companies_house_officer');
        INSERT INTO startup_external_ids (startup_id, id_type, external_id, source_name, details, match_confidence)
          VALUES (1,'company_number','09147492','uk_companies_house_company','{"date_of_creation": "2014-07-25"}','high');
        INSERT INTO investors (id, name, kind, tier_score) VALUES (1,'UB Forest Industry Green Growth Fund','climate-vc',0.85);
        INSERT INTO startup_investors VALUES (1,1,'lead','2024-09',1,'funding_rounds');
        INSERT INTO startup_peers VALUES (1,3,0.088,'["impact:D","kw:seaweed"]');
    """)
    conn.commit()
    conn.close()
    return client


def test_features_with_missing(seeded):
    body = seeded.get("/api/startups/notpla/features").json()
    assert body["as_of"] == "2026-10-17"
    got = {f["name"]: f for f in body["features"]}
    assert got["total_raised_usd"]["value"] == 48219216
    assert got["total_raised_usd"]["evidence"] == {"people_data_labs": 48219216}
    assert body["missing"] == ["no_round_24m"]  # unknown is reported, not zero-filled


def test_rounds_hide_nominal_by_default(seeded):
    assert [e["event_type"] for e in seeded.get("/api/startups/notpla/rounds").json()] == ["priced_allotment"]
    assert len(seeded.get("/api/startups/notpla/rounds?include_nominal=true").json()) == 2


def test_founders_with_ventures(seeded):
    [p] = seeded.get("/api/startups/notpla/founders").json()
    assert p["is_founder"] and p["ventures"][0]["company_name"] == "GRAVITY SKETCH LIMITED"
    assert p["ventures"][0]["before_startup"] is False


def test_investors_and_peers(seeded):
    [i] = seeded.get("/api/startups/notpla/investors").json()
    assert i["kind"] == "climate-vc" and i["role"] == "lead"
    [peer] = seeded.get("/api/startups/notpla/peers").json()
    assert peer["slug"] == "ocean-rainforest" and peer["shared_tags"] == ["impact:D", "kw:seaweed"]


def test_matrix_json_and_csv(seeded):
    body = seeded.get("/api/features").json()
    notpla = next(r for r in body["rows"] if r["slug"] == "notpla")
    assert notpla["total_raised_usd"] == 48219216 and notpla["no_round_24m"] is None
    csv_text = seeded.get("/api/features?format=csv").text
    assert csv_text.splitlines()[0].startswith("slug,name,as_of")
    assert seeded.get("/api/features/catalog").status_code == 200
