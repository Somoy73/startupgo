"""Scores in the StartupGo database (entities, facts, assessments): which startups need one, and what an entry stores."""

import json
import sqlite3
from pathlib import Path

import pytest

from startup_agent.database import StartupDatabase, domain, facts_of, missing_levels, needs_score, researched_within, scores_of
from startup_agent.errors import AgentError
from startup_agent.graph import build_agent_graph
from startup_agent.kth import score_crl, score_frl, score_iprl, score_tmrl
from startup_agent.navigator import kpi_codes, ocean_kpis
from startup_agent.scoring import score_all

from .helpers import fact

DB_DIR = Path(__file__).resolve().parents[3] / "DB"


# Two scored startups (one without a website), two to score; notpla has Navigator KPI evidence B2 at 2 and D1 at 1.
FIXTURE = """
INSERT INTO entities (id, key, kind, slug, name, website, domain, country, sector, tagline, description, stage, pipeline_stage) VALUES
  (1, 'startup:notpla', 'startup', 'notpla', 'Notpla', 'https://www.notpla.com', 'notpla.com', 'United Kingdom', 'Packaging',
   'Seaweed packaging', 'Seaweed-based packaging', 'series-a', 'diligence'),
  (2, 'startup:seaforester', 'startup', 'seaforester', 'SeaForester', NULL, NULL, 'Portugal', 'Habitat restoration', 'Kelp', 'Kelp', 'seed', 'sourced'),
  (3, 'startup:healix', 'startup', 'healix', 'Healix', 'https://healix.example', 'healix.example', NULL, NULL, NULL, NULL, 'unknown', 'sourced'),
  (4, 'startup:sammy', 'startup', 'sammy', 'Sammy', 'https://sammy.example', 'sammy.example', 'Unknown', 'Unknown', 'Unknown', 'Unknown',
   'unknown', 'sourced');
INSERT INTO assessments (entity_id, assessed_at, engine, assessor, confidence, crl, trl, brl, iprl, tmrl, frl) VALUES
  (1, '2026-10-16', 'seed-estimate', 'Startup Go seed estimate', 'low', 8, 8, 7, 6, 7, 8),
  (2, '2026-10-16', 'seed-estimate', 'Startup Go seed estimate', 'low', 4, 5, 4, 3, 5, 5);
INSERT INTO assessments (entity_id, assessed_at, engine, features) VALUES (3, '2026-10-17', 'startupgo-pipeline', '{}');
INSERT INTO facts (entity_id, section, field, value, evidence, source_url, source_type, source_name, status, confidence) VALUES
  (1, 'Api', 'navigator_kpi', '{"kpi": "B2", "level": 2, "claim": "Replaces plastic"}', 'Replaces plastic', NULL, 'manual', 'seed', 'claimed', 0.9),
  (1, 'Api', 'navigator_kpi', '{"kpi": "D1", "level": 1, "claim": "Lower CO2"}', 'Lower CO2', NULL, 'manual', 'seed', 'claimed', 0.9),
  (3, 'Api', 'reference', '{"title": "Healix raises"}', 'Healix raises', 'https://news.example/healix', 'manual', 'seed', 'claimed', 0.9),
  (3, 'A', 'business_id', '"1234567-8"', 'business id 1234567-8', NULL, 'registry', 'prh', 'verified', 0.95);
"""


def make_db(path: Path) -> StartupDatabase:
    conn = sqlite3.connect(path)
    conn.executescript((DB_DIR / "unified.sql").read_text())
    conn.executescript(FIXTURE)
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


def agent_runs(path: Path, slug: str):
    return rows(path, "SELECT a.* FROM assessments a JOIN entities e ON e.id = a.entity_id WHERE e.slug = ? AND a.engine = 'agent' "
                      "ORDER BY a.id", slug)


def with_seed_round(entry):
    entry["sections"]["G"]["facts"]["equity_rounds"] = [fact(
        "equity_rounds", {"stage": "seed", "date": "2025-05", "amount": 1500000, "currency": "eur", "investors": ["Blue Fund"]},
        source_type="news", status="verified").to_dict()]
    return entry


def test_new_startup_is_created_with_its_scores(tmp_path, entry):
    db = make_db(tmp_path / "db.sqlite")
    stored = db.save(with_seed_round(entry))
    assert (stored.slug, stored.created, stored.skipped) == ("acme-ocean", True, "")

    (startup,) = rows(db.path, "SELECT * FROM entities WHERE slug = 'acme-ocean'")
    assert (startup["kind"], startup["key"], startup["pipeline_stage"]) == ("startup", "startup:acme-ocean", "sourced")
    assert (startup["website"], startup["domain"], startup["country"], startup["tagline"]) == (
        "https://acme.fi/", "acme.fi", "Finland", "Sediment sensors for ports")
    (run,) = agent_runs(db.path, "acme-ocean")
    assert (run["id"], run["assessor"], run["trl"], run["tmrl"], run["judge_status"]) == (stored.assessment_id, "StartupGo agent", 6, 5,
                                                                                        entry["review"]["status"])
    assert len(run["assessed_at"]) == 19 and run["assessed_at"][10] == " "  # UTC, as SQLite's datetime('now')
    assert run["investment_score"] == entry["scores"]["investment_score"] and run["oir"] == entry["scores"]["ocean_impact_readiness"]["level"]
    assert len(json.loads(run["criteria"])) == 10 and json.loads(run["next_steps"]) == entry["next_steps"]
    basis = json.loads(run["levels_basis"])
    assert run["iprl"] == 1 and basis["iprl"]["level"] is None and "IPRL" in run["rationale"]  # no evidence: stored as 1
    assert basis["trl"]["level"] == 6 and basis["trl"]["evidence"]

    # The views read the scores like the older tables
    (readiness,) = rows(db.path, "SELECT * FROM readiness_assessments WHERE startup_id = ?", startup["id"])
    assert (readiness["assessor"], readiness["trl"]) == ("StartupGo agent", 6)
    assert rows(db.path, "SELECT slug FROM startups WHERE slug = 'acme-ocean'")
    assert {r["url"] for r in rows(db.path, "SELECT url FROM sources WHERE startup_id = ?", startup["id"])} >= {"https://acme.fi/technology"}
    (seed,) = rows(db.path, "SELECT * FROM funding_rounds WHERE startup_id = ?", startup["id"])
    assert (seed["round_type"], seed["announced_on"], seed["amount"], seed["currency"], seed["lead_investors"]) == (
        "seed", "2025-05", 1500000, "EUR", "Blue Fund")

    facts = rows(db.path, "SELECT * FROM facts WHERE entity_id = ? AND field NOT IN ('reference', 'navigator_kpi')", startup["id"])
    assert facts and {f["source_name"] for f in facts} == {"agent"} and all(f["is_current"] for f in facts)
    assert {f["section"] for f in facts if f["field"] == "equity_rounds"} == {"G"}


def test_saving_again_is_a_no_op_and_existing_startups_are_matched_by_domain(tmp_path, entry):
    db = make_db(tmp_path / "db.sqlite")
    conn = sqlite3.connect(db.path)
    conn.execute("INSERT INTO entities (key, kind, slug, name, tagline, description, sector, country, stage, pipeline_stage, website) "
                 "VALUES ('startup:acme', 'startup', 'acme', 'Acme', 'Analyst tagline', '', 'Ocean data', 'Unknown', 'seed', 'screening', "
                 "'http://www.acme.fi/')")
    conn.commit()
    conn.close()

    first = db.save(entry)
    assert (first.slug, first.created) == ("acme", False)
    (startup,) = rows(db.path, "SELECT * FROM entities WHERE slug = 'acme'")
    assert startup["tagline"] == "Analyst tagline" and startup["pipeline_stage"] == "screening"  # analyst data is kept
    assert startup["country"] == "Finland" and startup["description"]  # blanks are filled in
    facts = len(rows(db.path, "SELECT * FROM facts"))
    assert db.save(entry).skipped == "entry already stored"
    assert len(agent_runs(db.path, "acme")) == 1 and len(rows(db.path, "SELECT * FROM facts")) == facts


def test_a_blueinvest_candidate_becomes_a_startup(tmp_path, entry):
    db = make_db(tmp_path / "db.sqlite")
    conn = sqlite3.connect(db.path)
    conn.execute("INSERT INTO entities (id, key, kind, name, website, domain, sector, pipeline_stage, blueinvest_id) "
                 "VALUES (100001, 'blueinvest:807', 'candidate', 'Acme Oy', 'https://www.acme.fi', 'acme.fi', 'Blue tech', 'candidate', '807')")
    conn.commit()
    conn.close()
    stored = db.save(entry)
    assert (stored.slug, stored.created) == ("acme-oy", True)
    (startup,) = rows(db.path, "SELECT * FROM entities WHERE id = 100001")
    assert (startup["kind"], startup["slug"], startup["pipeline_stage"], startup["blueinvest_id"]) == ("startup", "acme-oy", "sourced", "807")
    assert startup["sector"] == "Blue tech"  # kept


def test_judged_runs_that_were_not_accepted_are_kept_without_a_score(tmp_path, entry):
    db = make_db(tmp_path / "db.sqlite")
    redo = {**entry, "review": {**entry["review"], "status": "redo_requested"}}
    stored = db.save(redo)  # a new startup: nothing to keep
    assert stored.skipped == "judge status redo_requested"
    assert not rows(db.path, "SELECT * FROM entities WHERE website = 'https://acme.fi/'")

    stored = db.save(redo, slug="sammy")  # a database startup: the run counts as research, without a score
    assert (stored.slug, stored.assessment_id, stored.skipped) == ("sammy", None, "judge status redo_requested")
    (run,) = agent_runs(db.path, "sammy")
    assert (run["judge_status"], run["trl"], run["oir"], run["investment_score"]) == ("redo_requested", None, None, None)
    assert json.loads(run["levels_basis"])["trl"]["level"] == 6
    assert not rows(db.path, "SELECT * FROM readiness_assessments WHERE startup_id = 4")
    assert not rows(db.path, "SELECT * FROM facts WHERE entity_id = 4")
    conn = db.connect()
    assert researched_within(conn, 4, 30) == run["assessed_at"] and needs_score(conn, 4)
    conn.close()
    assert db.save({**redo, "review": None}, slug="healix").skipped == "judge status missing"  # never judged: not a run
    assert not agent_runs(db.path, "healix")


def test_kpi_evidence_is_raised_but_never_lowered(tmp_path, entry):
    db = make_db(tmp_path / "db.sqlite")  # notpla: B2 at 2 (evidenced), D1 at 1 (claimed)
    facts = entry["sections"]["E"]["facts"]
    facts["impact_claim"] = fact("impact_claim", "Replaces plastic packaging").to_dict()  # B2 claimed: 1 < 2
    facts["impact_measured"] = [fact("impact_measured", {"metric": "CO2 avoided", "value": "40 t", "period": "2025"}).to_dict()]  # D1 measured: 3
    assert db.save(entry, slug="notpla").kpis == ["B2", "D1"]
    levels = {r["kpi_code"]: r["evidence_level"] for r in rows(db.path, "SELECT kpi_code, evidence_level FROM startup_ocean_kpis WHERE startup_id = 1")}
    assert levels == {"B2": 2, "D1": 3}
    (run,) = agent_runs(db.path, "notpla")
    assert {k: v["level"] for k, v in json.loads(run["navigator_kpis"]).items()} == {"B2": 1, "D1": 3}  # the agent's own evidence


def test_a_new_entry_replaces_the_agents_earlier_facts(tmp_path, entry):
    db = make_db(tmp_path / "db.sqlite")
    entry = with_seed_round(entry)
    db.save(entry, slug="sammy")
    db.save({**entry, "generated_at": "2026-12-01T10:00:00+02:00"}, slug="sammy")
    assert [r["assessed_at"] for r in agent_runs(db.path, "sammy")][-1] == "2026-12-01 08:00:00"
    agent_facts = "SELECT * FROM facts WHERE entity_id = 4 AND source_name = 'agent' AND field = ? AND is_current = 1"
    assert len(rows(db.path, agent_facts, "equity_rounds")) == 1 and len(rows(db.path, agent_facts, "dev_stage")) == 1
    assert len(rows(db.path, "SELECT * FROM funding_rounds WHERE startup_id = 4")) == 1


def test_a_round_stored_from_another_source_is_not_repeated(tmp_path, entry):
    db = make_db(tmp_path / "db.sqlite")
    conn = sqlite3.connect(db.path)
    conn.execute("""INSERT INTO facts (entity_id, section, field, value, source_type, source_name, status, confidence)
                    VALUES (4, 'G', 'equity_rounds', '{"round_type": "seed", "announced_on": "2025-05", "amount": 1600000}', 'news',
                            'funding_rounds', 'verified', 0.8)""")
    conn.commit()
    conn.close()
    db.save(with_seed_round(entry), slug="sammy")
    (seed,) = rows(db.path, "SELECT * FROM funding_rounds WHERE startup_id = 4")
    assert seed["amount"] == 1600000
    (kept,) = rows(db.path, "SELECT * FROM facts WHERE entity_id = 4 AND source_name = 'agent' AND field = 'equity_rounds'")
    assert kept["is_current"] == 0 and kept["observed_on"] == "2025-05"


def test_pending_lists_startups_without_a_usable_score(tmp_path, entry):
    db = make_db(tmp_path / "db.sqlite")
    pending = db.pending(limit=20, max_age_days=30)
    assert [c.slug for c in pending] == ["healix", "sammy"]  # notpla and seaforester are scored; seaforester has no website
    assert (pending[0].business_id, pending[0].extra_urls) == ("1234567-8", ("https://news.example/healix",))
    db.save(entry, slug="healix")
    assert [c.slug for c in db.pending(limit=20, max_age_days=30)] == ["sammy"]
    assert [c.slug for c in db.pending(limit=20, max_age_days=30, slugs=("notpla",))] == ["notpla"]
    assert db.known_domains()["notpla.com"] == "notpla"


def test_scores_without_trl_or_brl_evidence_are_researched_again(tmp_path):
    db = make_db(tmp_path / "db.sqlite")
    conn = db.connect()
    with conn:
        conn.execute("INSERT INTO assessments (entity_id, assessed_at, engine, crl, trl, brl, iprl, tmrl, frl, levels_basis) "
                     "VALUES (4, '2026-01-01 10:00:00', 'agent', 1, 6, 1, 1, 1, 1, ?)",
                     (json.dumps({d: {"level": 6 if d == "trl" else None} for d in ("crl", "trl", "brl", "iprl", "tmrl", "frl")}),))
    assert missing_levels(conn, 4) == ["crl", "brl", "iprl", "tmrl", "frl"] and needs_score(conn, 4)
    assert missing_levels(conn, 1) == [] and not needs_score(conn, 1)  # the seed estimate has no levels_basis: all known
    assert researched_within(conn, 4, 30) is None  # researched long ago
    conn.close()
    assert "sammy" in {c.slug for c in db.pending(limit=20, max_age_days=30)}


def test_older_databases_are_reported(tmp_path):
    conn = sqlite3.connect(tmp_path / "old.db")
    conn.execute("CREATE TABLE startups (id INTEGER PRIMARY KEY)")
    conn.close()
    with pytest.raises(AgentError, match="assessments, entities, facts"):
        StartupDatabase(tmp_path / "old.db").pending(limit=1, max_age_days=1)
    assert domain("HTTPS://www.Acme.fi:8080/x") == "acme.fi"


# --- the agent's rubric on database facts (scores_of, for the Backend) ----------------------------


def matrix(scores: dict) -> tuple:
    """What the Backend shows of a score: levels, criterion scores, investment score, confidence."""
    return (scores["trl"]["level"] if isinstance(scores["trl"], dict) else scores["trl"],
            scores["brl"]["level"] if isinstance(scores["brl"], dict) else scores["brl"],
            [(c["name"], c["score"], c["confidence"]) for c in scores["criteria"]],
            scores["investment_score"], scores["overall_confidence"])


def test_the_stored_facts_score_like_the_agents_entry(tmp_path, entry):
    db = make_db(tmp_path / "db.sqlite")
    stored = db.save(entry, slug="sammy")
    conn = db.connect()
    rescored = score_all(facts_of(conn, 4, today=entry["generated_at"][:10])).to_dict()
    assert matrix(rescored) == matrix(entry["scores"])  # same facts, same rubric, same scores
    agent = scores_of(conn, 4)
    conn.close()
    assert agent["source"] == "agent" and stored.assessment_id
    assert (agent["trl"], agent["brl"], agent["investment_score"], agent["overall_confidence"]) == matrix(entry["scores"])[:2] + matrix(entry["scores"])[3:]
    assert [c["score"] for c in agent["criteria"]] == [c["score"] for c in entry["scores"]["criteria"]]
    assert agent["investment_percent"] == entry["scores"]["investment_percent"]


def test_startups_the_agent_has_not_scored_get_the_rubric_on_their_facts(tmp_path):
    db = make_db(tmp_path / "db.sqlite")
    conn = db.connect()
    with conn:
        conn.executemany(
            "INSERT INTO facts (entity_id, section, field, value, evidence, source_type, source_name, status, confidence) VALUES (3, ?, ?, ?, 'q', ?, 'x', ?, 0.9)",
            [("C", "dev_stage", '"prototype_relevant_env"', "website", "claimed"),
             ("G", "equity_rounds", '{"stage": "seed", "date": "2025-05", "amount": 1500000, "currency": "EUR", "investors": ["Blue Fund"], "round_type": "seed"}',
              "news", "verified"),
             ("G", "stage", '"series_b_plus"', "manual", "claimed"),  # derived by the agent from the rounds, not read
             ("D", "revenue_trend", '"skyrocketing"', "website", "claimed")])  # outside the agent's vocabulary: left out
    facts = facts_of(conn, 3)
    assert facts["stage"].value == "seed" and "revenue_trend" not in facts and facts["equity_rounds"][0].value["amount"] == 1500000
    scores = scores_of(conn, 3, {"Tech": 2.0})
    conn.close()
    expected = score_all(facts, {"Tech": 2.0})
    assert scores["source"] == "facts" and scores["trl"] == expected.trl.level is not None
    assert (scores["investment_score"], scores["criteria"][7]["score"]) == (expected.investment_score, expected.criteria[7].score)


# --- Startups from the scrape agent ---------------------------------------------------------

SCRAPED = {"kind": "startup", "title": "Blue Kelp", "details": "Grows kelp for feed.", "website": "https://www.bluekelp.example/",
           "attributes": [{"name": "country", "value": "Norway"}, {"name": "what_it_does", "value": "Kelp farming for animal feed"}],
           "source_url": "https://pipeline.example/list", "quote": "Blue Kelp grows kelp for feed", "evidence": "page",
           "self_reported": False, "group": "BlueInvest pipeline"}


def test_a_scraped_startup_is_added_as_a_sourced_startup_with_its_evidence(tmp_path):
    db = make_db(tmp_path / "db.sqlite")
    assert db.add_scraped(SCRAPED) == {"slug": "blue-kelp", "name": "Blue Kelp", "status": "created"}

    entity = rows(db.path, "SELECT * FROM entities WHERE slug = 'blue-kelp'")[0]
    assert (entity["kind"], entity["pipeline_stage"], entity["domain"], entity["country"], entity["sector"]) == (
        "startup", "sourced", "bluekelp.example", "Norway", "Unknown")
    assert entity["tagline"] == "Kelp farming for animal feed"
    fact = rows(db.path, "SELECT * FROM facts WHERE entity_id = ?", entity["id"])[0]
    assert (fact["field"], fact["source_name"], fact["status"], fact["source_type"], fact["evidence"]) == (
        "scraped_record", "scraper", "verified", "news", "Blue Kelp grows kelp for feed")
    assert json.loads(fact["value"])["attributes"] == {"country": "Norway", "what_it_does": "Kelp farming for animal feed"}
    assert rows(db.path, "SELECT COUNT(*) n FROM assessments WHERE entity_id = ?", entity["id"])[0]["n"] == 0  # no score: research does that

    assert db.add_scraped(SCRAPED)["status"] == "exists"  # the same record again: no second startup, no second fact
    assert rows(db.path, "SELECT COUNT(*) n FROM facts WHERE entity_id = ?", entity["id"])[0]["n"] == 1


def test_a_scraped_record_of_a_known_startup_or_candidate_joins_it(tmp_path):
    db = make_db(tmp_path / "db.sqlite")
    conn = sqlite3.connect(db.path)
    conn.execute("INSERT INTO entities (key, kind, name, website) VALUES ('candidate:bi-1', 'candidate', 'Wave Co', 'https://waveco.example')")
    conn.commit()
    conn.close()

    own_site = {**SCRAPED, "title": "Notpla Ltd", "website": "", "source_url": "https://www.notpla.com/about", "self_reported": True}
    assert db.add_scraped(own_site, website="notpla.com") == {"slug": "notpla", "name": "Notpla", "status": "exists"}
    fact = rows(db.path, "SELECT status, source_type FROM facts WHERE entity_id = 1 AND source_name = 'scraper'")[0]
    assert (fact["status"], fact["source_type"]) == ("claimed", "website")  # the company's own page: a claim

    promoted = db.add_scraped({**SCRAPED, "title": "WaveCo", "website": "https://www.waveco.example", "evidence": "unverified"})
    assert promoted == {"slug": "wave-co", "name": "Wave Co", "status": "promoted"}
    row = rows(db.path, "SELECT kind, key, pipeline_stage FROM entities WHERE slug = 'wave-co'")[0]
    assert tuple(row) == ("startup", "candidate:bi-1", "sourced")
    assert rows(db.path, "SELECT status FROM facts WHERE entity_id = (SELECT id FROM entities WHERE slug = 'wave-co')")[0]["status"] == "inferred"

    with pytest.raises(AgentError, match="needs a name and a website"):
        db.add_scraped({**SCRAPED, "website": ""})
