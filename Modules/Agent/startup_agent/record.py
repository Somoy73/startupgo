"""The startup entry: facts grouped by section, plus scores, next steps and data gaps computed from them."""

from __future__ import annotations

import re
from dataclasses import dataclass, field
from typing import Any

from .derive import Facts, last_changed
from .facts import Fact
from .next_steps import data_gaps, next_steps
from .scoring import score_all
from .spec import FIELDS, SECTIONS, nullable, section_fields, value_schema
from .vocab import FACT_STATUSES, SOURCE_TYPES

SCHEMA_VERSION = "1.0"


def rank_key(entry: dict[str, Any]) -> tuple[bool, float, float]:
    """Sort key for evaluated entries: scored first, then by investment score and confidence."""
    scores = entry["scores"]
    score = scores["investment_score"]
    return (score is None, -(score or 0.0), -scores["overall_confidence"])


def slugify(text: str) -> str:
    return re.sub(r"[^a-z0-9]+", "-", text.lower()).strip("-") or "startup"


@dataclass(slots=True)
class StartupRecord:
    id: str
    name: str
    website: str
    generated_at: str
    facts: Facts
    sources: list[dict[str, Any]] = field(default_factory=list)
    rejected: list[dict[str, Any]] = field(default_factory=list)
    errors: list[dict[str, Any]] = field(default_factory=list)
    lead: dict[str, Any] | None = None
    review: dict[str, Any] | None = None  # the judge's verdict and history

    def to_dict(self, *, weights: dict[str, float] | None = None) -> dict[str, Any]:
        """Serialize, recomputing scores and next steps from the current facts."""
        changed = last_changed(self.facts)
        facts = {**self.facts, "last_changed": self._last_changed_fact(changed)}
        scores = score_all(facts, weights)
        return {
            "schema_version": SCHEMA_VERSION,
            "id": self.id,
            "name": self.name,
            "website": self.website,
            "generated_at": self.generated_at,
            "lead": self.lead,
            "sections": {
                sid: {
                    "title": section.title,
                    "last_changed": changed.get(sid),
                    "facts": {spec.name: _serialize(facts.get(spec.name)) for spec in section_fields(sid)},
                }
                for sid, section in SECTIONS.items()
            },
            "scores": scores.to_dict(),
            "next_steps": [s.to_dict() for s in next_steps(facts, scores, today=self.generated_at[:10])],
            "data_gaps": [g.to_dict() for g in data_gaps(facts)],
            "sources": self.sources,
            "rejected_extractions": self.rejected,
            "errors": self.errors,
            "review": self.review,
        }

    def _last_changed_fact(self, changed: dict[str, str]) -> Fact | None:
        if not changed:
            return None
        return Fact("last_changed", changed, "Most recent retrieved_at per section", "", "manual", self.generated_at[:10], "inferred", 1.0)

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> StartupRecord:
        facts: Facts = {}
        for section in data["sections"].values():
            for name, entry in section["facts"].items():
                if name == "last_changed":
                    continue
                if isinstance(entry, list):
                    facts[name] = [Fact.from_dict(e) for e in entry]
                elif isinstance(entry, dict):
                    facts[name] = Fact.from_dict(entry)
        return cls(
            id=data["id"],
            name=data["name"],
            website=data["website"],
            generated_at=data["generated_at"],
            facts=facts,
            sources=data.get("sources", []),
            rejected=data.get("rejected_extractions", []),
            errors=data.get("errors", []),
            lead=data.get("lead"),
            review=data.get("review"),
        )


def _serialize(entry: Fact | list[Fact] | None) -> Any:
    if entry is None:
        return None
    if isinstance(entry, list):
        return [f.to_dict() for f in entry]
    return entry.to_dict()


# --- JSON Schema export ----------------------------------------------------------------


def record_json_schema() -> dict[str, Any]:
    """JSON Schema (draft 2020-12) for the facts part of a startup entry."""

    def fact_schema(name: str, value: dict[str, Any]) -> dict[str, Any]:
        return {
            "type": "object",
            "properties": {
                "field": {"const": name},
                "value": value,
                "evidence": {"type": "string", "description": "Verbatim quote, under 40 words"},
                "source_url": {"type": "string"},
                "source_type": {"enum": list(SOURCE_TYPES)},
                "retrieved_at": {"type": "string", "format": "date"},
                "status": {"enum": list(FACT_STATUSES)},
                "confidence": {"type": "number", "minimum": 0, "maximum": 1},
            },
            "required": ["field", "value", "evidence", "source_url", "source_type", "retrieved_at", "status", "confidence"],
        }

    sections: dict[str, Any] = {}
    for sid, section in SECTIONS.items():
        props: dict[str, Any] = {}
        for spec in section_fields(sid):
            if spec.name == "last_changed":
                value: dict[str, Any] = {"type": "object", "additionalProperties": {"type": "string", "format": "date"}}
            elif spec.is_list:
                value = value_schema(spec.kind, spec.enum, spec.props)["items"]
            else:
                value = value_schema(spec.kind, spec.enum, spec.props)
            fact = fact_schema(spec.name, value)
            schema = {"type": "array", "items": fact} if spec.is_list else fact
            props[spec.name] = nullable(schema) | {"description": f"{spec.description} Feeds: {', '.join(spec.feeds) or '-'}."}
        sections[sid] = {
            "type": "object",
            "title": section.title,
            "properties": {
                "title": {"const": section.title},
                "last_changed": nullable({"type": "string", "format": "date"}),
                "facts": {"type": "object", "properties": props, "required": list(props)},
            },
        }
    return {
        "$schema": "https://json-schema.org/draft/2020-12/schema",
        "title": "StartupGo startup entry",
        "description": "Facts with evidence per the Ocean Opportunity Radar extraction schema. Null means unknown, not no.",
        "type": "object",
        "properties": {
            "schema_version": {"const": SCHEMA_VERSION},
            "id": {"type": "string"},
            "name": {"type": "string"},
            "website": {"type": "string"},
            "generated_at": {"type": "string", "format": "date-time"},
            "sections": {"type": "object", "properties": sections, "required": list(sections)},
            "scores": {"type": "object"},
            "next_steps": {"type": "array"},
            "data_gaps": {"type": "array"},
            "sources": {"type": "array"},
            "rejected_extractions": {"type": "array"},
            "errors": {"type": "array"},
        },
        "required": ["schema_version", "id", "name", "website", "generated_at", "sections", "scores"],
        "$comment": f"{len(FIELDS)} fields in {len(SECTIONS)} sections",
    }
