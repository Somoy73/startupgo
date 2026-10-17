"""What gets indexed: one text document per entity in the StartupGo database and per agent entry.

The database is the 3-table model (DB/unified.sql): entities, facts, assessments. A database document
combines the entity's own row (name, tagline, description, sector, location, stage), its current facts
of the fields in FACT_FIELDS (the strongest fact for one-value fields, every distinct one for list
fields), the latest assessment with readiness levels (each level's meaning from readiness_levels) and
its ocean-impact evidence (navigator_kpi facts, with ocean_kpis / ocean_impact_areas names).

Left out: facts found by name only (news, research papers), page dumps (website text, web history),
job ads and code repositories (they would add many off-topic entities), beneficial owners (personal
data), and workflow state (pipeline_stage, analyst notes), which changes often: each change would mean
processing the entity again.

Each document is kept under MAX_CHARS, so LightRAG makes one chunk of it: no extra chunks, and one
entity-extraction call per entity. Documents come best first (assessed entities, then those with the
most evidence), so process-storage --limit N processes the top N.

A document's id is the entity's key ("startup:notpla", "blueinvest:84") or "entry:<id>" for an agent
entry. It is also LightRAG's file_path, so every retrieved entity, relation and chunk leads back to
the entity it came from. An agent entry whose website matches a database entity is found as it.
"""

from __future__ import annotations

import hashlib
import json
import logging
import re
import sqlite3
from collections.abc import Iterable
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any
from urllib.parse import urlparse

from .errors import SearchError

log = logging.getLogger(__name__)

DEFAULT_KINDS = ("startup",)  # entity kinds indexed unless [sources] kinds says otherwise
MAX_CHARS = 3600  # ~900 tokens: under LightRAG's 1200-token chunk, so one chunk per document
MAX_ITEMS = 6  # lines per list section
EVIDENCE_LEVELS = {1: "claimed", 2: "qualitative evidence", 3: "measured", 4: "third-party verified"}
STATUS_ORDER = {"verified": 0, "claimed": 1, "inferred": 2}
LEVEL_COLUMNS = ("crl", "trl", "brl", "iprl", "tmrl", "frl")
ENUM_TOKEN = re.compile(r"^[a-z0-9]+(?:_[a-z0-9]+)+$")
SKIPPED_FACTS = {"last_changed"}

# Fact fields put into a document: field -> label. List fields keep every distinct value.
FACT_FIELDS = {
    "solution_summary": "Solution",
    "blueinvest_summary": "Solution",
    "blue_sector": "Blue economy sector",
    "dev_stage": "Development stage",
    "stage": "Funding stage",
    "legal_form": "Legal form",
    "registry_status": "Registry status",
    "status": "Registry status",
    "team_size": "Team size",
    "employee_range": "Employees",
    "revenue_last_fy": "Revenue last financial year",
    "total_raised": "Total raised",
    "current_raise": "Raising now",
}
LIST_FIELDS = {
    "impact_claim",
    "impact_pathway",
    "navigator_kpi",
    "equity_rounds",
    "grants",
    "accelerators",
    "investor",
    "patents",
    "founders",
    "advisors_board",
    "insolvency_case",
    "reference",
}


@dataclass(frozen=True, slots=True)
class Document:
    id: str
    text: str
    name: str
    website: str | None
    startup: str | None  # slug of the database startup it describes (kind "startup" only)
    entry: str | None = None  # agent entry it was built from
    info: dict[str, Any] = field(default_factory=dict)  # info returned with search matches
    key: str | None = None  # database entity it describes (own key, or the entity an agent entry is linked to)
    kind: str = "entry"  # entity kind (startup, candidate, ...) or "entry" for an unlinked agent entry

    @property
    def digest(self) -> str:
        return hashlib.sha256(self.text.encode("utf-8")).hexdigest()

    def metadata(self) -> dict[str, Any]:
        """What the index remembers about the document to turn search hits into results."""
        return {
            "digest": self.digest,
            "key": self.key or self.id,
            "kind": self.kind,
            "name": self.name,
            "website": self.website,
            "startup": self.startup,
            "entry": self.entry,
            "info": self.info,
        }


def load_documents(database: Path, entries: Path, kinds: Iterable[str] = DEFAULT_KINDS) -> list[Document]:
    """Documents for the database entities of ``kinds`` (best first), then every agent entry."""
    if not database.exists():
        raise SearchError(f"database not found: {database}")
    conn = sqlite3.connect(f"file:{database}?mode=ro", uri=True)
    try:
        documents = database_documents(conn, kinds)
    finally:
        conn.close()
    by_domain = {d: doc for doc in documents if (d := domain(doc.website))}
    return documents + entry_documents(entries, by_domain)


# --- StartupGo database: entities, facts, assessments --------------------------------------------


def database_documents(conn: sqlite3.Connection, kinds: Iterable[str] = DEFAULT_KINDS) -> list[Document]:
    """One document per entity of ``kinds``, best first: assessed ones, then the ones with most evidence."""
    kinds = tuple(kinds)
    tables = {r[0] for r in conn.execute("SELECT name FROM sqlite_master WHERE type = 'table'")}
    if missing := {"entities", "facts", "assessments"} - tables:
        raise SearchError(f"the database has no {', '.join(sorted(missing))} table: use the unified database (DB/startupgo_unified.db)")
    if not kinds:
        return []
    reference = _Reference(conn)
    marks = ",".join("?" * len(kinds))
    ranked = []
    for row in _rows(conn, f"SELECT * FROM entities WHERE kind IN ({marks}) ORDER BY key", kinds):
        facts = _facts(conn, row["id"])
        assessment = _latest_levels(conn, row["id"])
        slug = row["slug"] if row["kind"] == "startup" else None
        document = Document(
            id=row["key"],
            text=_entity_text(row, facts, assessment, reference),
            name=row["name"],
            website=row["website"],
            startup=slug,
            info={key: row[key] for key in ("tagline", "sector", "country", "city", "stage")},
            key=row["key"],
            kind=row["kind"],
        )
        ranked.append(((assessment is None, -len(facts), -sum(map(len, facts.values())), row["name"].casefold()), document))
    return [document for _, document in sorted(ranked, key=lambda pair: pair[0])]


class _Reference:
    """The fixed vocabularies: readiness dimensions and levels, ocean KPIs and impact areas."""

    def __init__(self, conn: sqlite3.Connection):
        self.dimensions = {r["code"]: r["name"] for r in _rows(conn, "SELECT code, name FROM readiness_dimensions ORDER BY sort_order")}
        self.meanings = {(r["dimension_code"], r["level"]): r["summary"] for r in _rows(conn, "SELECT * FROM readiness_levels")}
        self.kpis = {
            r["code"]: (r["area"], r["name"])
            for r in _rows(conn, "SELECT o.code, o.name, a.name AS area FROM ocean_kpis o JOIN ocean_impact_areas a ON a.code = o.area_code")
        }


def _facts(conn: sqlite3.Connection, entity_id: int) -> dict[str, list[Any]]:
    """Current facts of the indexed fields: field -> values, strongest first (verified, then confidence, then newest)."""
    names = sorted({*FACT_FIELDS, *LIST_FIELDS})
    rows = _rows(
        conn,
        f"SELECT f.field, f.value, f.status, f.confidence, f.source_name, r.name AS related FROM facts f "
        f"LEFT JOIN entities r ON r.id = f.related_entity_id "
        f"WHERE f.entity_id = ? AND f.is_current = 1 AND f.field IN ({','.join('?' * len(names))}) "
        f"ORDER BY f.observed_on DESC NULLS LAST, f.id DESC",
        (entity_id, *names),
    )
    rows.sort(key=lambda r: (STATUS_ORDER.get(r["status"], 3), -(r["confidence"] or 0)))  # stable: newest first within a tie
    facts: dict[str, list[Any]] = {}
    for r in rows:
        try:
            value = json.loads(r["value"]) if r["value"] else None
        except json.JSONDecodeError:
            value = r["value"]
        if value in (None, "", [], {}):
            continue
        if isinstance(value, dict):
            value = {**value, "_source": r["source_name"], "_related": r["related"]}
        values = facts.setdefault(r["field"], [])
        if value not in values:
            values.append(value)
    return facts


def _latest_levels(conn: sqlite3.Connection, entity_id: int) -> dict[str, Any] | None:
    """The latest assessment that has readiness levels; assessments with only features don't count."""
    rows = _rows(
        conn,
        "SELECT * FROM assessments WHERE entity_id = ? AND (trl IS NOT NULL OR brl IS NOT NULL) ORDER BY assessed_at DESC, id DESC LIMIT 1",
        (entity_id,),
    )
    return rows[0] if rows else None


def _entity_text(row: dict[str, Any], facts: dict[str, list[Any]], assessment: dict[str, Any] | None, ref: _Reference) -> str:
    city, country = row["city"], row["country"]
    location = f"{city}, {country}" if city and country and city != country else (country or city)
    head = [f"# {row['name']}"]
    if row["tagline"]:
        head.append(row["tagline"])
    if row["description"] and row["description"] != row["tagline"]:
        head += ["", row["description"]]
    summaries = [s for s in _one_each(facts, ("solution_summary", "blueinvest_summary")) if s not in (row["description"], row["tagline"])]
    if summaries:
        head += ["", _clip(summaries[0], 900)]
    head.append("")
    for label, value in (
        ("Sector", row["sector"]),
        ("Location", location),
        ("Stage", row["stage"]),
        ("Founded", row["founded_year"]),
        ("Website", row["website"]),
    ):
        if value:
            head.append(f"{label}: {value}")
    shown = set()
    for name, label in FACT_FIELDS.items():
        if name in ("solution_summary", "blueinvest_summary") or label in shown or not facts.get(name):
            continue
        if facts[name][0] == "other":  # an uninformative vocabulary value
            continue
        shown.add(label)
        head.append(f"{label}: {_value_text(name, facts[name][0])}")

    sections = [
        ("Readiness", _readiness_lines(assessment, ref)),
        ("Ocean impact", _impact_lines(facts, ref)),
        ("Funding", _funding_lines(facts)),
        ("Investors", [f"- {_text(v.get('name') or v.get('_related'))}" + (f" ({v['role']})" if v.get("role") else "") for v in facts.get("investor", [])]),
        ("Patents", [_patent_line(v) for v in facts.get("patents", []) if isinstance(v, dict)]),
        ("Team", _team_lines(facts)),
        ("Risks", [f"- {_text(v.get('title'))}" for v in facts.get("insolvency_case", []) if isinstance(v, dict)]),
        ("Sources", [f"- {_text(v.get('title'))}" for v in facts.get("reference", []) if isinstance(v, dict) and v.get("title")]),
    ]
    return _fit(head, sections, MAX_CHARS)


def _readiness_lines(a: dict[str, Any] | None, ref: _Reference) -> list[str]:
    if a is None:
        return []
    lines = [f"KTH Innovation Readiness Level 1-9, assessed {a['assessed_at'][:10]}" + (f", {a['confidence']} confidence" if a["confidence"] else "")]
    for column in LEVEL_COLUMNS:
        level = a[column]
        if level is not None:
            code = column.upper()
            meaning = ref.meanings.get((code, level))
            lines.append(f"- {ref.dimensions.get(code, code)} ({code}) {level}" + (f": {meaning}" if meaning else ""))
    if a["oir"] is not None:
        lines.append(f"- Ocean impact readiness {a['oir']} of 5")
    if a["rationale"]:
        lines.append(_clip(a["rationale"], 400))
    return lines


def _impact_lines(facts: dict[str, list[Any]], ref: _Reference) -> list[str]:
    lines = []
    for kpi in facts.get("navigator_kpi", []):
        if not isinstance(kpi, dict) or not kpi.get("level"):
            continue
        area, name = ref.kpis.get(kpi.get("kpi"), ("", kpi.get("kpi") or "KPI"))
        evidence = EVIDENCE_LEVELS.get(kpi["level"], f"level {kpi['level']}")
        lines.append(f"- {area}, {name} ({kpi.get('kpi')}): {_text(kpi.get('claim'))} ({evidence})".replace("- , ", "- "))
    claims = [c for c in _one_each(facts, ("impact_claim", "impact_pathway")) if not any(c in line for line in lines)]
    return lines + [f"- {_text(c)}" for c in claims]


def _funding_lines(facts: dict[str, list[Any]]) -> list[str]:
    rounds = [r for r in facts.get("equity_rounds", []) if isinstance(r, dict)]
    rounds.sort(key=lambda r: str(r.get("announced_on") or r.get("date") or ""), reverse=True)
    lines = [_round_line(r) for r in rounds]
    lines += [_grant_line(g) for g in facts.get("grants", []) if isinstance(g, dict)]
    lines += [f"- Accelerator: {_text(a.get('programme'))}" for a in facts.get("accelerators", []) if isinstance(a, dict)]
    return lines


def _round_line(r: dict[str, Any]) -> str:
    kind = r.get("round_type") or r.get("stage")
    if r.get("_source") == "uk_sh01" and kind in (None, "other"):
        kind = "share allotment"
    line = f"- {_text(kind) or 'round'}: {_amount(r.get('amount'), r.get('currency'))}"
    if when := r.get("announced_on") or r.get("date"):
        line += f" ({when})"
    leads = r.get("lead_investors") or _text(r.get("investors"))
    if leads:
        line += f", led by {leads}" if r.get("lead_investors") else f", investors {leads}"
    if r.get("notes"):
        line += f". {r['notes']}"
    return line


def _grant_line(g: dict[str, Any]) -> str:
    line = f"- Grant: {_text(g.get('programme')) or 'programme'} from {_text(g.get('funder')) or 'a funder'}"
    if g.get("amount") is not None:
        line += f", {_amount(g['amount'], g.get('currency'))}"
    if g.get("year"):
        line += f" ({g['year']})"
    if g.get("role"):
        line += f", {_text(g['role'])}"
    flags = [label for key, label in (("eic", "EIC"), ("mission_ocean", "EU Mission Ocean")) if g.get(key)]
    return line + (f" [{', '.join(flags)}]" if flags else "")


def _patent_line(p: dict[str, Any]) -> str:
    status = "granted" if p.get("granted") else _text(p.get("legal_status")).lower() or "filed"
    return f"- {_text(p.get('title')) or p.get('number')} ({p.get('number')}, {p.get('year')}, {status})"


def _team_lines(facts: dict[str, list[Any]]) -> list[str]:
    lines = []
    for person in facts.get("founders", []):
        if isinstance(person, dict) and (name := person.get("name") or person.get("_related")):
            role = _text(person.get("role")) or "founder"
            lines.append(f"- {name}, {role}" + ("" if person.get("active", True) else " (former)"))
    for person in facts.get("advisors_board", []):
        if isinstance(person, dict) and (name := person.get("name") or person.get("_related")):
            lines.append(f"- {name}, board ({_text(person.get('background')) or 'member'})")
    return lines


def _fit(head: list[str], sections: list[tuple[str, list[str]]], budget: int) -> str:
    """The head, then each section's first MAX_ITEMS lines (all of Readiness), while the text stays under ``budget`` characters."""
    text = "\n".join(head).strip()
    for title, lines in sections:
        for number, line in enumerate(lines if title == "Readiness" else lines[:MAX_ITEMS]):
            block = f"\n\n## {title}\n{line}" if number == 0 else f"\n{line}"
            if len(text) + len(block) > budget:
                break
            text += block
    return text[:budget].strip() + "\n"


def _one_each(facts: dict[str, list[Any]], names: tuple[str, ...]) -> list[str]:
    """Distinct text values of ``names``, in order."""
    return list(dict.fromkeys(v.strip() for n in names for v in facts.get(n, []) if isinstance(v, str) and v.strip()))


def _value_text(name: str, value: Any) -> str:
    if name in ("total_raised", "revenue_last_fy") and isinstance(value, (int, float)):
        return _amount(value, None)
    if name == "current_raise" and isinstance(value, dict):
        return _amount(value.get("amount"), value.get("currency")) + (" (open)" if value.get("open") else "")
    return _text({k: v for k, v in value.items() if not k.startswith("_")} if isinstance(value, dict) else value)


def _amount(amount: Any, currency: Any) -> str:
    if not isinstance(amount, (int, float)):
        return "undisclosed amount"
    return f"{amount:,.0f} {currency or ''}".strip()


def _clip(text: str, limit: int) -> str:
    text = " ".join(text.split())
    return text if len(text) <= limit else text[: limit - 1].rsplit(" ", 1)[0] + "…"


def _rows(conn: sqlite3.Connection, sql: str, params: tuple[Any, ...] = ()) -> list[dict[str, Any]]:
    """Rows as dicts, whatever row factory the connection uses."""
    cursor = conn.execute(sql, params)
    names = [column[0] for column in cursor.description]
    return [dict(zip(names, row)) for row in cursor.fetchall()]


# --- Agent entries --------------------------------------------------------------------------------


def entry_documents(directory: Path, by_domain: dict[str, Document]) -> list[Document]:
    """One document per agent entry (Agent/output/startups/*.json); unreadable files are skipped."""
    if not directory.is_dir():
        log.warning("no agent entries at %s", directory)
        return []
    documents = []
    for path in sorted(directory.glob("*.json")):
        try:
            data = json.loads(path.read_text(encoding="utf-8"))
            documents.append(entry_document(data, by_domain))
        except (OSError, json.JSONDecodeError, KeyError, TypeError, AttributeError) as exc:
            log.warning("skipped agent entry %s: %s", path.name, exc)
    return documents


def entry_document(data: dict[str, Any], by_domain: dict[str, Document]) -> Document:
    scores = data.get("scores") or {}
    summary = {
        "trl": (scores.get("trl") or {}).get("level"),
        "brl": (scores.get("brl") or {}).get("level"),
        "ocean_impact_readiness": (scores.get("ocean_impact_readiness") or {}).get("level"),
        "investment_score": scores.get("investment_score"),
        "overall_confidence": scores.get("overall_confidence"),
    }
    linked = by_domain.get(domain(data.get("website")) or "")
    return Document(
        id=f"entry:{data['id']}",
        text=entry_text(data, summary),
        name=data["name"],
        website=data.get("website"),
        startup=linked.startup if linked else None,
        entry=data["id"],
        info=summary,
        key=linked.key if linked else None,
        kind=linked.kind if linked else "entry",
    )


def entry_text(data: dict[str, Any], summary: dict[str, Any]) -> str:
    lines = [f"# {data['name']}"]
    if data.get("website"):
        lines.append(f"Website: {data['website']}")
    sections = []
    for section in data.get("sections", {}).values():
        facts = [
            line
            for name, fact in section.get("facts", {}).items()
            if name not in SKIPPED_FACTS
            for line in _fact_lines(name, fact)
        ]
        if facts:
            sections.append((section["title"], facts))

    levels = [
        f"{label} {summary[key]} of {scale}"
        for key, label, scale in (("trl", "TRL", 9), ("brl", "BRL", 9), ("ocean_impact_readiness", "Ocean impact readiness", 5))
        if summary[key] is not None
    ]
    if summary["investment_score"] is not None:
        levels.append(f"investment score {summary['investment_score']} (confidence {summary['overall_confidence']})")
    if levels:
        sections.insert(0, ("StartupGo agent assessment", ["; ".join(levels)]))
    return _fit(lines, sections, MAX_CHARS)


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
    """Host without "www.", to match an agent entry's website with a database entity's."""
    if not url:
        return None
    host = urlparse(url if "://" in url else f"https://{url}").hostname or ""
    return host.casefold().removeprefix("www.") or None
