"""Documents built from the StartupGo database and agent entries."""

import json
import sqlite3
from pathlib import Path

import pytest

from startup_search.documents import (
    MAX_CHARS,
    database_documents,
    domain,
    entry_document,
    load_documents,
)
from startup_search.errors import SearchError

DB_DIR = Path(__file__).resolve().parents[3] / "DB"


def fact(entity_id, section, field, value, *, status="verified", source="funding_rounds", related=None, current=1):
    return (entity_id, section, field, json.dumps(value), related, source, source, status, 0.9, current)


@pytest.fixture
def database(tmp_path):
    """The 3-table model (DB/unified.sql): two assessed startups, one with facts only, one bare, a candidate."""
    path = tmp_path / "startupgo_unified.db"
    conn = sqlite3.connect(path)
    conn.executescript((DB_DIR / "unified.sql").read_text())
    conn.executemany(
        "INSERT INTO entities (id, key, kind, slug, name, website, country, city, sector, tagline, description, founded_year, stage) "
        "VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)",
        [
            (1, "startup:notpla", "startup", "notpla", "Notpla", "https://www.notpla.com", "United Kingdom", "London", "Materials & packaging",
             "Seaweed-based packaging that replaces single-use plastic", "Packaging made from seaweed.", 2014, "series-a"),
            (2, "startup:ocean-rainforest", "startup", "ocean-rainforest", "Ocean Rainforest", None, "Faroe Islands", "Faroe Islands",
             "Aquaculture", "Offshore seaweed farming", "Farms seaweed offshore.", 2010, "seed"),
            (3, "startup:sammy", "startup", "sammy", "SAMMY", "https://sammyacht.com", "Greece", "Patra", None, None, "Marina berth booking.", None, None),
            (4, "startup:bare", "startup", "bare", "Bare", None, "Spain", None, None, None, None, None, None),
            (5, "blueinvest:84", "candidate", None, "Skizo", None, None, None, "Coastal protection", None, "We transform marine litter in fashion products", None, None),
            (100, "investor:ub", "investor", None, "UB Forest Industry Green Growth Fund", None, None, None, None, None, None, None, None),
        ],
    )
    conn.executemany(
        "INSERT INTO assessments (entity_id, assessed_at, engine, confidence, crl, trl, brl, iprl, tmrl, frl, rationale) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)",
        [
            (1, "2026-10-16", "seed-estimate", "low", 8, 8, 7, 6, 7, 8, "Products on the market."),
            (2, "2026-10-16", "seed-estimate", "low", 6, 7, 6, 5, 6, 6, None),
        ],
    )
    conn.execute("INSERT INTO assessments (entity_id, assessed_at, engine, features) VALUES (3, '2026-10-17', 'startupgo-pipeline', '{}')")
    conn.executemany(
        "INSERT INTO facts (entity_id, section, field, value, related_entity_id, source_type, source_name, status, confidence, is_current) "
        "VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)",
        [
            fact(1, "X", "navigator_kpi", {"kpi": "B2", "level": 2, "claim": "Replaces single-use plastic items."}, status="claimed"),
            fact(1, "G", "equity_rounds", {"round_type": "series-a", "amount": 20000000.0, "currency": "GBP", "announced_on": "2024-09",
                                           "lead_investors": "UB Forest Industry Green Growth Fund"}),
            fact(1, "G", "equity_rounds", {"date": "2021-09-24", "stage": "other", "amount": 10000001.62, "currency": "GBP"}, source="uk_sh01"),
            fact(1, "G", "grants", {"funder": "European Commission", "programme": "HORIZON NO-PLASTI-CUPS", "amount": 708878.45, "currency": "EUR",
                                    "year": 2025, "role": "coordinator", "eic": False}, source="cordis_projects"),
            fact(1, "C", "patents", {"number": "EP3601061B1", "title": "Method of encapsulating liquid products", "year": 2017, "granted": "2023-03-08"}),
            fact(1, "X", "investor", {"name": "UB Forest Industry Green Growth Fund", "role": "lead"}, related=100),
            fact(1, "X", "reference", {"title": "EU Maritime Forum: Notpla Series A+"}, status="claimed", source="manual"),
            fact(1, "A", "team_size", 78, status="claimed", source="people_data_labs"),
            fact(1, "A", "team_size", 12, status="claimed", source="old_source", current=0),  # not current
            fact(1, "J", "news", {"headline": "Notpla wins a prize"}, source="google_news_rss"),  # found by name: left out
            fact(1, "X", "research_paper", {"title": "Notpla, n."}, status="inferred", source="openalex"),
            fact(3, "B", "solution_summary", "Smart marina services for yachters.", status="claimed", source="blueinvest_profile"),
            fact(3, "C", "dev_stage", "commercial_operation", status="claimed", source="blueinvest_profile"),
            fact(3, "B", "blue_sector", "other", status="inferred", source="seed"),
            fact(3, "F", "founders", {"name": "Jane Doe", "role": "ceo", "active": True}, source="registry"),
            fact(5, "C", "dev_stage", "prototype", status="claimed", source="blueinvest_profile"),
        ],
    )
    conn.commit()
    conn.close()
    return path


def entry(**overrides):
    data = {
        "id": "notpla-com",
        "name": "Notpla",
        "website": "https://notpla.com/",
        "sections": {
            "B": {
                "title": "Blue-economy profile",
                "facts": {
                    "blue_sector": {"value": "blue_biotechnology", "status": "inferred"},
                    "customer_type": {"value": ["B2B", "B2C"], "status": "claimed"},
                    "ocean_problem": None,
                },
            },
            "G": {
                "title": "Funding and deal",
                "facts": {
                    "grants": [{"value": {"funder": "EIC", "amount": 2500000, "currency": "EUR", "programme": None}}],
                    "current_raise": {"value": {"amount": 1000, "open": True}, "status": "claimed"},
                },
            },
            "J": {"title": "Signals", "facts": {"last_changed": {"value": {"A": "2026-10-17"}}}},
        },
        "scores": {
            "trl": {"level": 7},
            "brl": {"level": 5},
            "ocean_impact_readiness": {"level": 3},
            "investment_score": 3.4,
            "overall_confidence": 0.6,
        },
    }
    return {**data, **overrides}


def test_one_document_per_database_startup_best_first(database):
    conn = sqlite3.connect(database)
    docs = database_documents(conn)
    # Assessed first (most evidence first), then by evidence; candidates and investors aren't startups.
    assert [d.id for d in docs] == ["startup:notpla", "startup:ocean-rainforest", "startup:sammy", "startup:bare"]
    assert all((d.kind, d.key, d.startup) == ("startup", d.id, d.id.removeprefix("startup:")) for d in docs)

    notpla = docs[0].text
    for expected in (
        "# Notpla\nSeaweed-based packaging that replaces single-use plastic\n\nPackaging made from seaweed.",
        "Sector: Materials & packaging",
        "Location: London, United Kingdom",
        "Team size: 78\n",  # the current fact
        "assessed 2026-10-16, low confidence",
        "- Technology (TRL) 8: Complete technology proven in actual operations by first users.",
        "- Funding (FRL) 8: Term-sheet-level discussions; due-diligence materials ready.",
        "- A clean ocean, Volume of macro-plastic diverted from nature (or landfill) (B2): Replaces single-use plastic items. (qualitative evidence)",
        "- series-a: 20,000,000 GBP (2024-09), led by UB Forest Industry Green Growth Fund",
        "- share allotment: 10,000,002 GBP (2021-09-24)",
        "- Grant: HORIZON NO-PLASTI-CUPS from European Commission, 708,878 EUR (2025), coordinator",
        "## Investors\n- UB Forest Industry Green Growth Fund (lead)",
        "- Method of encapsulating liquid products (EP3601061B1, 2017, granted)",
        "## Sources\n- EU Maritime Forum: Notpla Series A+",
    ):
        assert expected in notpla
    assert "prize" not in notpla and "Notpla, n." not in notpla  # facts found by name only aren't indexed
    assert "pipeline" not in notpla.lower()  # workflow state (pipeline_stage, notes) isn't indexed
    assert docs[0].info == {
        "tagline": "Seaweed-based packaging that replaces single-use plastic",
        "sector": "Materials & packaging",
        "country": "United Kingdom",
        "city": "London",
        "stage": "series-a",
    }
    assert "Location: Faroe Islands\n" in docs[1].text  # city == country: once

    sammy = docs[2].text
    assert "Smart marina services for yachters." in sammy and "Development stage: commercial operation" in sammy
    assert "## Readiness" not in sammy  # its assessment has features only
    assert "Blue economy sector" not in sammy  # "other" says nothing
    assert "## Team\n- Jane Doe, ceo" in sammy


def test_other_entity_kinds_are_indexed_when_asked(database):
    docs = database_documents(sqlite3.connect(database), ("startup", "candidate"))
    skizo = next(d for d in docs if d.id == "blueinvest:84")
    assert (skizo.kind, skizo.key, skizo.startup) == ("candidate", "blueinvest:84", None)
    assert "We transform marine litter in fashion products" in skizo.text and "Development stage: prototype" in skizo.text


def test_a_document_fits_one_chunk(database):
    conn = sqlite3.connect(database)
    rows = [fact(1, "C", "patents", {"number": f"EP{i}", "title": "Seaweed film " * 20, "year": 2020}) for i in range(40)]
    conn.executemany(
        "INSERT INTO facts (entity_id, section, field, value, related_entity_id, source_type, source_name, status, confidence, is_current) "
        "VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)",
        rows,
    )
    conn.execute("UPDATE entities SET description = ? WHERE id = 1", ("Long description. " * 300,))
    notpla = database_documents(conn)[0].text
    assert len(notpla) <= MAX_CHARS and notpla.startswith("# Notpla")


def test_a_database_without_the_three_tables_is_rejected(tmp_path):
    conn = sqlite3.connect(tmp_path / "old.db")
    conn.execute("CREATE TABLE startups (id INTEGER PRIMARY KEY, slug TEXT)")
    with pytest.raises(SearchError, match="no assessments, entities, facts table: use the unified database"):
        database_documents(conn)


def test_entry_facts_become_readable_lines():
    doc = entry_document(entry(), {})
    assert doc.id == "entry:notpla-com" and doc.entry == "notpla-com" and doc.startup is None
    lines = doc.text.splitlines()
    assert "Blue sector: blue biotechnology" in lines  # enum tokens read as words
    assert "Customer type: B2B, B2C" in lines
    assert "- Grants: funder: EIC; amount: 2,500,000; currency: EUR" in lines  # nulls dropped
    assert "Current raise: amount: 1000; open: yes" in lines
    assert not any(line.startswith(("Ocean problem", "Last changed")) for line in lines)
    assert "TRL 7 of 9; BRL 5 of 9; Ocean impact readiness 3 of 5; investment score 3.4 (confidence 0.6)" in lines
    assert doc.info == {"trl": 7, "brl": 5, "ocean_impact_readiness": 3, "investment_score": 3.4, "overall_confidence": 0.6}


def test_entry_is_linked_to_the_database_startup_with_the_same_website(database, tmp_path):
    entries = tmp_path / "entries"
    entries.mkdir()
    (entries / "notpla-com.json").write_text(json.dumps(entry()))
    (entries / "kelpco.json").write_text(json.dumps(entry(id="kelpco", name="KelpCo", website="kelp.co")))
    (entries / "broken.json").write_text("{not json")

    docs = {d.id: d for d in load_documents(database, entries)}
    notpla = docs["entry:notpla-com"]  # https://www.notpla.com in the database
    assert (notpla.startup, notpla.key, notpla.kind) == ("notpla", "startup:notpla", "startup")
    assert (docs["entry:kelpco"].startup, docs["entry:kelpco"].key, docs["entry:kelpco"].kind) == (None, None, "entry")
    assert list(docs)[-2:] == ["entry:kelpco", "entry:notpla-com"]  # agent entries after the database
    assert "entry:broken" not in docs


def test_missing_database_is_an_error(tmp_path):
    with pytest.raises(SearchError, match="database not found"):
        load_documents(tmp_path / "nope.db", tmp_path)


@pytest.mark.parametrize(
    ("url", "expected"),
    [("https://www.Notpla.com/about", "notpla.com"), ("notpla.com", "notpla.com"), ("", None), (None, None)],
)
def test_domain(url, expected):
    assert domain(url) == expected
