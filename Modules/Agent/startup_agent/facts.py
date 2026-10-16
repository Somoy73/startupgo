"""The fact envelope, its status/confidence policy, and value validation."""

from __future__ import annotations

import re
from dataclasses import asdict, dataclass
from typing import Any

from .spec import FieldSpec, Kind, Prop
from .vocab import FactStatus, SourceType

# Base extractor confidence by source. Registry and grant data default to 0.95 (schema).
SOURCE_CONFIDENCE: dict[str, float] = {
    "registry": 0.95,
    "grant_db": 0.95,
    "eu_projects": 0.9,
    "patent": 0.9,
    "manual": 0.9,
    "news": 0.8,
    "website": 0.7,
    "pitch_deck": 0.7,
}
# Independent sources verify; the startup's own material only claims.
VERIFYING_SOURCES = {"registry", "grant_db", "eu_projects", "patent", "news", "manual"}
CLASSIFIED_PENALTY = 0.85  # value is an LLM classification of the quote, not the quote itself
FRAGMENT_MATCH_PENALTY = 0.9  # quote matched only as "..."-separated fragments
INFERRED_CONFIDENCE = 0.6  # default for code-derived facts

STATUS_RANK = {"verified": 3, "claimed": 2, "inferred": 1}

_DATE = re.compile(r"^\d{4}(-\d{2}(-\d{2})?)?$")


@dataclass(slots=True)
class Fact:
    field: str
    value: Any
    evidence: str
    source_url: str
    source_type: SourceType
    retrieved_at: str
    status: FactStatus
    confidence: float

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> Fact:
        return cls(**{k: data[k] for k in cls.__dataclass_fields__})


def status_for(source_type: str, *, classified: bool) -> FactStatus:
    if classified:
        return "inferred"
    return "verified" if source_type in VERIFYING_SOURCES else "claimed"


def confidence_for(source_type: str, *, classified: bool, exact_quote: bool = True) -> float:
    confidence = SOURCE_CONFIDENCE.get(source_type, 0.5)
    if classified:
        confidence *= CLASSIFIED_PENALTY
    if not exact_quote:
        confidence *= FRAGMENT_MATCH_PENALTY
    return round(confidence, 2)


def better(a: Fact | None, b: Fact | None) -> Fact | None:
    """Pick the stronger of two facts for the same field: verified beats claimed, then confidence."""
    if a is None or b is None:
        return a or b
    return max((a, b), key=lambda f: (STATUS_RANK[f.status], f.confidence))


# --- Value validation ----------------------------------------------------------------------


class InvalidValue(ValueError):
    pass


def coerce(spec: FieldSpec, value: Any) -> Any:
    """Validate an LLM value against the field spec. Returns None for empty values."""
    return _coerce(spec.kind, value, spec.enum, spec.props)


def _coerce(kind: Kind, value: Any, enum: tuple[str, ...] = (), props: dict[str, Prop] | None = None) -> Any:
    if value is None:
        return None
    match kind:
        case "text" | "sentence":
            if not isinstance(value, str):
                raise InvalidValue(f"expected text, got {type(value).__name__}")
            text = " ".join(value.split())
            return text or None
        case "integer":
            if isinstance(value, bool) or not isinstance(value, (int, float)) or int(value) != value:
                raise InvalidValue(f"expected an integer, got {value!r}")
            return int(value)
        case "number":
            if isinstance(value, bool) or not isinstance(value, (int, float)):
                raise InvalidValue(f"expected a number, got {value!r}")
            return value
        case "date":
            if not isinstance(value, str) or not _DATE.match(value.strip()):
                raise InvalidValue(f"expected YYYY, YYYY-MM or YYYY-MM-DD, got {value!r}")
            return value.strip()
        case "boolean":
            if not isinstance(value, bool):
                raise InvalidValue(f"expected true/false, got {value!r}")
            return value
        case "enum":
            if value not in enum:
                raise InvalidValue(f"{value!r} is not one of {', '.join(enum)}")
            return value
        case "enum_list" | "text_list":
            if not isinstance(value, list):
                raise InvalidValue("expected a list")
            item_kind: Kind = "enum" if kind == "enum_list" else "text"
            items = [_coerce(item_kind, item, enum) for item in value]
            unique = list(dict.fromkeys(i for i in items if i is not None))
            return unique or None
        case "object" | "object_list":
            if not isinstance(value, dict):
                raise InvalidValue("expected an object")
            cleaned = {name: _coerce(p.kind, value.get(name), p.enum) for name, p in (props or {}).items()}
            return cleaned if any(v is not None for v in cleaned.values()) else None
    raise InvalidValue(f"unknown kind {kind}")
