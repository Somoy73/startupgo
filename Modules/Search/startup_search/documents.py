"""What gets indexed: one text document per startup in the StartupGo database and per agent entry.

A document's id is also its LightRAG file_path ("startup:<slug>" or "entry:<id>"), so every
retrieved entity, relation and chunk leads back to the startup it came from. An agent entry whose
website matches a database startup is linked to that startup and found as it.
"""

from __future__ import annotations

import hashlib
import json
import logging
import re
import sqlite3
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any
from urllib.parse import urlparse

from .errors import SearchError

log = logging.getLogger(__name__)

EVIDENCE_LEVELS = {1: "claimed", 2: "qualitative evidence", 3: "measured", 4: "third-party verified"}
ENUM_TOKEN = re.compile(r"^[a-z0-9]+(?:_[a-z0-9]+)+$")
SKIPPED_FACTS = {"last_changed"}


@dataclass(frozen=True, slots=True)
class Document:
    id: str
    text: str
    name: str
    website: str | None
    startup: str | None  # slug of the database startup it describes
    entry: str | None = None  # agent entry it was built from
    info: dict[str, Any] = field(default_factory=dict)  # startup info returned with search matches

    @property
    def digest(self) -> str:
        return hashlib.sha256(self.text.encode("utf-8")).hexdigest()

    def metadata(self) -> dict[str, Any]:
        """What the index remembers about the document to turn search hits into results."""
        return {
            "digest": self.digest,
            "name": self.name,
            "website": self.website,
            "startup": self.startup,
            "entry": self.entry,
            "info": self.info,
        }


def load_documents(database: Path, entries: Path) -> list[Document]:
    """Documents for every database startup and every agent entry, database first."""
    if not database.exists():
        raise SearchError(f"database not found: {database}")
    conn = sqlite3.connect(f"file:{database}?mode=ro", uri=True)
    try:
        startups = database_documents(conn)
    finally:
        conn.close()
    by_domain = {d: doc.startup for doc in startups if (d := domain(doc.website)) and doc.startup}
    return startups + entry_documents(entries, by_domain)


# --- StartupGo database ---------------------------------------------------------------------------


def database_documents(conn: sqlite3.Connection) -> list[Document]:
    dimensions = _rows(conn, "SELECT code, name FROM readiness_dimensions ORDER BY sort_order")
    return [
        Document(
            id=f"startup:{row['slug']}",
            text=_startup_text(conn, row, dimensions),
            name=row["name"],
            website=row["website"],
            startup=row["slug"],
            info={key: row[key] for key in ("tagline", "sector", "country", "city", "stage")},
        )
        for row in _rows(conn, "SELECT * FROM startups ORDER BY slug")
    ]


def _startup_text(conn: sqlite3.Connection, row: dict[str, Any], dimensions: list[dict[str, Any]]) -> str:
    city, country = row["city"], row["country"]
    location = f"{city}, {country}" if city and city != country else country
    lines = [
        f"# {row['name']}",
        row["tagline"],
        "",
        row["description"],
        "",
        f"Sector: {row['sector']}",
        f"Location: {location}",
        f"Stage: {row['stage']}",
    ]
    if row["founded_year"]:
        lines.append(f"Founded: {row['founded_year']}")
    if row["website"]:
        lines.append(f"Website: {row['website']}")

    assessment = _rows(
        conn,
        "SELECT * FROM readiness_assessments WHERE startup_id = ? ORDER BY assessed_on DESC, id DESC LIMIT 1",
        (row["id"],),
    )
    if assessment:
        a = assessment[0]
        levels = ", ".join(f"{d['name']} ({d['code']}) {a[d['code'].lower()]}" for d in dimensions)
        lines += ["", f"## Readiness (KTH Innovation Readiness Level 1-9, assessed {a['assessed_on']})", levels]
        if a["rationale"]:
            lines.append(a["rationale"])

    kpis = _rows(
        conn,
        "SELECT a.name AS area, o.code, o.name, k.evidence_level, k.claim FROM startup_ocean_kpis k "
        "JOIN ocean_kpis o ON o.code = k.kpi_code JOIN ocean_impact_areas a ON a.code = o.area_code "
        "WHERE k.startup_id = ? AND k.evidence_level > 0 ORDER BY o.code",
        (row["id"],),
    )
    if kpis:
        lines += ["", "## Ocean impact"]
        lines += [f"- {k['area']}, {k['name']} ({k['code']}): {k['claim']} ({EVIDENCE_LEVELS[k['evidence_level']]})" for k in kpis]

    rounds = _rows(
        conn,
        "SELECT * FROM funding_rounds WHERE startup_id = ? ORDER BY announced_on DESC NULLS LAST, id DESC",
        (row["id"],),
    )
    if rounds:
        lines += ["", "## Funding"]
        lines += [_round_line(r) for r in rounds]
    return "\n".join(lines).strip() + "\n"


def _round_line(r: dict[str, Any]) -> str:
    amount = f"{r['amount']:,.0f} {r['currency'] or ''}".strip() if r["amount"] is not None else "undisclosed amount"
    line = f"- {r['round_type']}: {amount}"
    if r["announced_on"]:
        line += f" ({r['announced_on']})"
    if r["lead_investors"]:
        line += f", led by {r['lead_investors']}"
    if r["notes"]:
        line += f". {r['notes']}"
    return line


def _rows(conn: sqlite3.Connection, sql: str, params: tuple[Any, ...] = ()) -> list[dict[str, Any]]:
    """Rows as dicts, whatever row factory the connection uses."""
    cursor = conn.execute(sql, params)
    names = [column[0] for column in cursor.description]
    return [dict(zip(names, row)) for row in cursor.fetchall()]


# --- Agent entries --------------------------------------------------------------------------------


def entry_documents(directory: Path, startups_by_domain: dict[str, str]) -> list[Document]:
    """One document per agent entry (Agent/output/startups/*.json); unreadable files are skipped."""
    if not directory.is_dir():
        log.warning("no agent entries at %s", directory)
        return []
    documents = []
    for path in sorted(directory.glob("*.json")):
        try:
            data = json.loads(path.read_text(encoding="utf-8"))
            documents.append(entry_document(data, startups_by_domain))
        except (OSError, json.JSONDecodeError, KeyError, TypeError, AttributeError) as exc:
            log.warning("skipped agent entry %s: %s", path.name, exc)
    return documents


def entry_document(data: dict[str, Any], startups_by_domain: dict[str, str]) -> Document:
    scores = data.get("scores") or {}
    summary = {
        "trl": (scores.get("trl") or {}).get("level"),
        "brl": (scores.get("brl") or {}).get("level"),
        "ocean_impact_readiness": (scores.get("ocean_impact_readiness") or {}).get("level"),
        "investment_score": scores.get("investment_score"),
        "overall_confidence": scores.get("overall_confidence"),
    }
    return Document(
        id=f"entry:{data['id']}",
        text=entry_text(data, summary),
        name=data["name"],
        website=data.get("website"),
        startup=startups_by_domain.get(domain(data.get("website")) or ""),
        entry=data["id"],
        info=summary,
    )


def entry_text(data: dict[str, Any], summary: dict[str, Any]) -> str:
    lines = [f"# {data['name']}"]
    if data.get("website"):
        lines.append(f"Website: {data['website']}")
    for section in data.get("sections", {}).values():
        facts = [
            line
            for name, fact in section.get("facts", {}).items()
            if name not in SKIPPED_FACTS
            for line in _fact_lines(name, fact)
        ]
        if facts:
            lines += ["", f"## {section['title']}", *facts]

    levels = [
        f"{label} {summary[key]} of {scale}"
        for key, label, scale in (("trl", "TRL", 9), ("brl", "BRL", 9), ("ocean_impact_readiness", "Ocean impact readiness", 5))
        if summary[key] is not None
    ]
    if summary["investment_score"] is not None:
        levels.append(f"investment score {summary['investment_score']} (confidence {summary['overall_confidence']})")
    if levels:
        lines += ["", "## StartupGo agent assessment", "; ".join(levels)]
    return "\n".join(lines).strip() + "\n"


def _fact_lines(name: str, fact: Any) -> list[str]:
    """A fact envelope (or a list of them, for list fields) as readable lines; empty facts give none."""
    label = name.replace("_", " ").capitalize()
    if isinstance(fact, list):
        values = [text for item in fact if isinstance(item, dict) and (text := _text(item.get("value")))]
        return [f"- {label}: {value}" for value in values]
    if isinstance(fact, dict) and (value := _text(fact.get("value"))):
        return [f"{label}: {value}"]
    return []


def _text(value: Any) -> str:
    if value is None:
        return ""
    if isinstance(value, bool):
        return "yes" if value else "no"
    if isinstance(value, (int, float)):
        return f"{value:,}" if abs(value) >= 10000 else str(value)
    if isinstance(value, str):
        return value.replace("_", " ") if ENUM_TOKEN.match(value) else value.strip()
    if isinstance(value, list):
        return ", ".join(text for item in value if (text := _text(item)))
    if isinstance(value, dict):
        return "; ".join(f"{k.replace('_', ' ')}: {text}" for k, v in value.items() if (text := _text(v)))
    return str(value)


def domain(url: str | None) -> str | None:
    """Host without "www.", to match an agent entry's website with a database startup's."""
    if not url:
        return None
    host = urlparse(url if "://" in url else f"https://{url}").hostname or ""
    return host.casefold().removeprefix("www.") or None
