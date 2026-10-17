"""Features, funding, founders, investors and peers: read from the unified database's facts and assessments."""

import sqlite3

import pytest

from app.db import db_path

ENDPOINTS = ["features", "rounds", "founders", "investors", "peers"]


@pytest.mark.parametrize("ep", ENDPOINTS)
def test_unknown_startup_is_404(client, ep):
    assert client.get(f"/api/startups/nope/{ep}").status_code == 404


def test_the_unified_database_has_them_for_seed_startups(client):
    body = client.get("/api/startups/notpla/features").json()
    assert body["as_of"] and {f["name"] for f in body["features"]} >= {"total_raised_usd"}
    rounds = client.get("/api/startups/notpla/rounds").json()
    assert {"announced_round", "priced_round", "eu_grant"} <= {r["event_type"] for r in rounds}
    assert client.get("/api/startups/notpla/investors").json()
    assert client.get("/api/features/catalog").json()


@pytest.fixture()
def seeded(client):
    """testco: features, rounds from two sources, a founder with an earlier company, a lead investor, a peer."""
    conn = sqlite3.connect(db_path())
    conn.executescript("""
        INSERT INTO entities (id, key, kind, slug, name, sector, pipeline_stage) VALUES
          (900, 'startup:testco', 'startup', 'testco', 'TestCo', 'Packaging', 'sourced'),
          (901, 'person:ch:abc', 'person', NULL, 'PASLIER, Pierre-Yves', NULL, NULL),
          (902, 'investor:ub-forest', 'investor', NULL, 'UB Forest Industry Green Growth Fund', NULL, NULL);
        INSERT INTO assessments (entity_id, assessed_at, engine, features, peers) VALUES
          (900, '2027-01-01', 'startupgo-pipeline',
           '{"total_raised_usd": {"value": 48219216, "text": null, "evidence": {"people_data_labs": 48219216}},
             "lead_investors": {"value": null, "text": "UB Forest", "evidence": null}}',
           '[{"name": "Notpla", "similarity": 0.088, "source": "startupgo"}, {"name": "Kelp Project", "similarity": 0.3, "trl": 6, "source": "blueinvest"}]');
        INSERT INTO facts (entity_id, section, field, value, related_entity_id, evidence, source_url, source_type, source_name, status,
                           confidence, observed_on) VALUES
          (900, 'G', 'equity_rounds', '{"date": "2021-09-24", "stage": "other", "amount": 10000001.62, "currency": "GBP", "investors": [],
             "price_per_share": 5.2969, "allotments": 1}', NULL, 'SH01', 'https://ch.example/sh01', 'registry', 'uk_sh01', 'verified', 0.95, '2021-09-24'),
          (900, 'G', 'equity_rounds', '{"round_type": "series-a", "amount": 20000000, "currency": "GBP", "announced_on": "2024-09",
             "lead_investors": "UB Forest", "stage": "series_a"}', NULL, 'series-a', NULL, 'news', 'funding_rounds', 'claimed', 0.8, '2024-09'),
          (900, 'G', 'total_raised', '48219216', NULL, 'PDL', NULL, 'manual', 'people_data_labs', 'claimed', 0.9, NULL),
          (900, 'A', 'founded_date', '"2014-07-25"', NULL, 'registration', NULL, 'registry', 'uk_companies_house_company', 'verified', 0.95, '2014-07-25'),
          (900, 'F', 'founders', '{"name": "PASLIER, Pierre-Yves", "role": "director", "technical": null, "prior_startup": null, "active": true}',
             901, 'director', NULL, 'registry', 'uk_companies_house_company', 'verified', 0.95, '2014-07-25'),
          (900, 'F', 'advisors_board', '{"name": "Board Member", "background": "non-executive director"}', NULL, 'board', NULL, 'registry',
             'uk_companies_house_company', 'verified', 0.95, '2020-01-01'),
          (901, 'X', 'venture', '{"company": "GRAVITY SKETCH LIMITED", "company_number": "09215060", "status": "active", "role": "director",
             "from": "2014-09-22", "to": "2016-04-08"}', NULL, 'officer', NULL, 'registry', 'uk_companies_house_officer', 'verified', 0.95, '2014-09-22'),
          (901, 'X', 'education', '[{"school": "TU Delft", "degrees": ["master of science"]}]', NULL, 'PDL', NULL, 'manual', 'people_data_labs',
             'claimed', 0.9, NULL),
          (900, 'X', 'investor', '{"name": "UB Forest Industry Green Growth Fund", "role": "lead", "rounds": 1, "first_seen": "2024-09"}', 902,
             'lead', NULL, 'news', 'funding_rounds', 'verified', 0.8, '2024-09'),
          (902, 'X', 'investor_profile', '{"kind": "climate-vc", "tier_score": 0.85}', NULL, 'tier', NULL, 'manual', 'investor_tiers', 'claimed',
             0.9, NULL);
    """)
    conn.commit()
    conn.close()
    return client


def test_features_with_missing(seeded):
    body = seeded.get("/api/startups/testco/features").json()
    assert body["as_of"] == "2027-01-01"
    got = {f["name"]: f for f in body["features"]}
    assert got["total_raised_usd"]["value"] == 48219216 and got["total_raised_usd"]["feature_group"] == "rounds"
    assert got["total_raised_usd"]["evidence"] == {"people_data_labs": 48219216}
    assert "no_round_24m" in body["missing"] and "total_raised_usd" not in body["missing"]  # unknown is reported, not zero-filled


def test_rounds_from_every_source(seeded):
    rounds = seeded.get("/api/startups/testco/rounds").json()
    assert [(r["event_type"], r["event_date"]) for r in rounds] == [("priced_round", "2021-09-24"), ("announced_round", "2024-09"),
                                                                    ("aggregate", None)]
    assert (rounds[0]["price_per_share"], rounds[0]["status"], rounds[1]["round_label"]) == (5.2969, "verified", "series-a")


def test_founders_with_ventures(seeded):
    [p] = seeded.get("/api/startups/testco/founders").json()
    assert p["is_founder"] and p["active"] and p["ventures"][0]["company_name"] == "GRAVITY SKETCH LIMITED"
    assert p["ventures"][0]["before_startup"] is False and p["education"][0]["degrees"] == ["master of science"]
    people = seeded.get("/api/startups/testco/founders", params={"founders_only": False}).json()
    assert [(p["name"], p["is_founder"]) for p in people] == [("PASLIER, Pierre-Yves", True), ("Board Member", False)]


def test_investors_and_peers(seeded):
    [i] = seeded.get("/api/startups/testco/investors").json()
    assert (i["kind"], i["tier_score"], i["role"]) == ("climate-vc", 0.85, "lead")
    [peer] = seeded.get("/api/startups/testco/peers").json()
    assert (peer["slug"], peer["name"], peer["similarity"]) == ("notpla", "Notpla", 0.088)


def test_matrix_json_and_csv(seeded):
    body = seeded.get("/api/features").json()
    testco = next(r for r in body["rows"] if r["slug"] == "testco")
    assert testco["total_raised_usd"] == 48219216 and testco["lead_investors"] == "UB Forest" and testco["no_round_24m"] is None
    csv_text = seeded.get("/api/features?format=csv").text
    assert csv_text.splitlines()[0].startswith("slug,name,as_of")
