"""One LLM call per section: structured output, forced quotes, null allowed, quotes verified in code."""

from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

from .documents import SourceDocument, locate_quote
from .facts import Fact, InvalidValue, coerce, confidence_for, status_for
from .llm import LLMClient
from .spec import FieldSpec, SectionSpec, nullable, section_fields, value_schema

MAX_QUOTE_WORDS = 60  # prompt asks for < 40; allow some slack before rejecting


@dataclass(slots=True)
class Rejection:
    field: str
    value: Any
    evidence: str | None
    source_url: str | None
    reason: str

    def to_dict(self) -> dict[str, Any]:
        return {k: getattr(self, k) for k in self.__dataclass_fields__}


@dataclass(slots=True)
class SectionResult:
    facts: dict[str, Fact | list[Fact] | None] = field(default_factory=dict)
    rejected: list[Rejection] = field(default_factory=list)


@dataclass(frozen=True, slots=True)
class PromptTemplates:
    system: str
    section: str

    @classmethod
    def load(cls, system_path: Path, section_path: Path) -> PromptTemplates:
        return cls(system_path.read_text(encoding="utf-8").strip(), section_path.read_text(encoding="utf-8").strip())


_STRING_OR_NULL = nullable({"type": "string"})


def response_schema(fields: list[FieldSpec]) -> dict[str, Any]:
    """JSON Schema for one section's LLM response: every field wrapped with evidence and source_url."""
    properties: dict[str, Any] = {}
    for f in fields:
        if f.is_list:
            item = value_schema(f.kind, f.enum, f.props)["items"]
            properties[f.name] = {
                "type": "array",
                "description": f.description,
                "items": {
                    "type": "object",
                    "properties": {"item": item, "evidence": {"type": "string"}, "source_url": {"type": "string"}},
                    "required": ["item", "evidence", "source_url"],
                    "additionalProperties": False,
                },
            }
        else:
            properties[f.name] = {
                "type": "object",
                "description": f.description,
                "properties": {
                    "value": nullable(value_schema(f.kind, f.enum, f.props)),
                    "evidence": _STRING_OR_NULL,
                    "source_url": _STRING_OR_NULL,
                },
                "required": ["value", "evidence", "source_url"],
                "additionalProperties": False,
            }
    return {"type": "object", "properties": properties, "required": list(properties), "additionalProperties": False}


def field_guide(fields: list[FieldSpec]) -> str:
    lines = []
    for f in fields:
        kind = {"object_list": "list of items", "enum": "one of", "enum_list": "any of"}.get(f.kind, f.kind)
        allowed = f": {', '.join(f.enum)}" if f.enum else ""
        props = f" (item fields: {', '.join(f.props)})" if f.props else ""
        lines.append(f"- {f.name} [{kind}{allowed}]{props}: {f.description}")
    return "\n".join(lines)


def render_documents(documents: list[SourceDocument]) -> str:
    return "\n\n".join(
        f"=== Document {i}\nsource_url: {d.url}\ntitle: {d.title}\n\n{d.text}" for i, d in enumerate(documents, 1)
    )


class SectionExtractor:
    def __init__(self, llm: LLMClient, prompts: PromptTemplates):
        self.llm = llm
        self.prompts = prompts

    def extract(
        self, section: SectionSpec, *, startup_name: str, website: str, documents: list[SourceDocument]
    ) -> SectionResult:
        fields = section_fields(section.id, origin="llm")
        result = SectionResult()
        if not fields or not documents:
            return result

        user = self.prompts.section.format(
            startup_name=startup_name,
            website=website,
            section_id=section.id,
            section_title=section.title,
            section_note=section.note,
            field_guide=field_guide(fields),
            documents=render_documents(documents),
        )
        data = self.llm.complete_json(system=self.prompts.system, user=user, schema=response_schema(fields))

        for spec in fields:
            raw = data.get(spec.name)
            if spec.is_list:
                entries = raw if isinstance(raw, list) else []
                facts = [
                    fact
                    for entry in entries
                    if isinstance(entry, dict)
                    and (fact := self._fact(spec, entry.get("item"), entry.get("evidence"), entry.get("source_url"), documents, result))
                ]
                result.facts[spec.name] = facts or None
            else:
                entry = raw if isinstance(raw, dict) else {}
                result.facts[spec.name] = self._fact(
                    spec, entry.get("value"), entry.get("evidence"), entry.get("source_url"), documents, result
                )
        return result

    @staticmethod
    def _fact(
        spec: FieldSpec,
        value: Any,
        evidence: Any,
        source_url: Any,
        documents: list[SourceDocument],
        result: SectionResult,
    ) -> Fact | None:
        def reject(reason: str) -> None:
            result.rejected.append(Rejection(spec.name, value, evidence, source_url, reason))

        try:
            value = coerce(spec, value)
        except InvalidValue as exc:
            reject(f"invalid value: {exc}")
            return None
        if value is None:
            return None
        if not isinstance(evidence, str) or not evidence.strip():
            reject("no evidence quote")
            return None
        if len(evidence.split()) > MAX_QUOTE_WORDS:
            reject(f"evidence longer than {MAX_QUOTE_WORDS} words")
            return None
        doc, exact = locate_quote(evidence, documents, source_url if isinstance(source_url, str) else None)
        if doc is None:
            reject("evidence quote not found in any source document")
            return None
        return Fact(
            field=spec.name,
            value=value,
            evidence=" ".join(evidence.split()),
            source_url=doc.url,
            source_type=doc.source_type,
            retrieved_at=doc.retrieved_at,
            status=status_for(doc.source_type, classified=spec.classified),
            confidence=confidence_for(doc.source_type, classified=spec.classified, exact_quote=exact),
        )
