"""Documents built from the StartupGo database and agent entries."""

import json
import sqlite3
from pathlib import Path

import pytest

from startup_search.documents import database_documents, domain, entry_document, load_documents
from startup_search.errors import SearchError

DB_DIR = Path(__file__).resolve().parents[3] / "DB"


@pytest.fixture
def database(tmp_path):
    path = tmp_path / "startupgo.db"
    conn = sqlite3.connect(path)
    conn.executescript((DB_DIR / "schema.sql").read_text())
    conn.executescript((DB_DIR / "seed.sql").read_text())
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


def test_one_document_per_database_startup(database):
    conn = sqlite3.connect(database)
    docs = {d.id: d for d in database_documents(conn)}
    assert len(docs) == 8 and all(d.startup == d.id.removeprefix("startup:") for d in docs.values())

    notpla = docs["startup:notpla"].text
    for expected in (
        "# Notpla",
        "Sector: Materials & packaging",
        "Location: London, United Kingdom",
        "Technology (TRL) 8",
        "A clean ocean",
        "(qualitative evidence)",
        "- series-a: 20,000,000 GBP (2024-09), led by UB Forest Industry Green Growth Fund",
    ):
        assert expected in notpla
    assert "Location: Faroe Islands\n" in docs["startup:ocean-rainforest"].text  # city == country: once
    assert docs["startup:notpla"].info == {
        "tagline": "Seaweed-based packaging that replaces single-use plastic",
        "sector": "Materials & packaging",
        "country": "United Kingdom",
        "city": "London",
        "stage": "series-a",
    }


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
    assert docs["entry:notpla-com"].startup == "notpla"  # https://www.notpla.com in the database
    assert docs["entry:kelpco"].startup is None
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
