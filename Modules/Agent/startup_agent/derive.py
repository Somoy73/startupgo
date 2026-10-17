"""Facts computed by code from other facts (status "inferred")."""

from __future__ import annotations

import re
from typing import Any

from .facts import INFERRED_CONFIDENCE, Fact
from .spec import FIELDS_BY_NAME

Facts = dict[str, Fact | list[Fact] | None]

# Approximate static FX to EUR, only used for total_raised.
FX_TO_EUR = {"EUR": 1.0, "USD": 0.93, "GBP": 1.17, "SEK": 0.087, "NOK": 0.086, "DKK": 0.134, "CHF": 1.05}
ROUND_ORDER = ("pre_seed", "seed", "series_a", "series_b_plus")

_ROLE_PATTERNS = {
    "CEO / business lead": re.compile(r"\b(ceo|chief executive|managing director|general manager|president)\b"),
    "technical lead": re.compile(r"\b(cto|chief technology|technical|engineer|engineering|scientist|r&d|research)\b"),
    "commercial lead": re.compile(r"\b(cco|chief commercial|cmo|sales|commercial|business development|marketing|revenue)\b"),
}


def items(facts: Facts, name: str) -> list[Fact]:
    value = facts.get(name)
    if value is None:
        return []
    return value if isinstance(value, list) else [value]


def value(facts: Facts, name: str) -> Any:
    fact = facts.get(name)
    return fact.value if isinstance(fact, Fact) else None


def _derived(name: str, value: Any, basis: str, inputs: list[Fact], today: str) -> Fact:
    # The schema's source_type enum has no "derived" value; derived facts use "manual" with no URL.
    confidence = min((f.confidence for f in inputs), default=INFERRED_CONFIDENCE)
    return Fact(name, value, basis, "", "manual", today, "inferred", round(confidence, 2))


def key_roles_missing(facts: Facts, today: str) -> Fact | None:
    founders = items(facts, "founders")
    if not founders:
        return None  # unknown team, not "nothing missing"
    roles = " ".join((f.value.get("role") or "").lower() for f in founders)
    missing = [label for label, pattern in _ROLE_PATTERNS.items() if not pattern.search(roles)]
    if any(f.value.get("technical") for f in founders) and "technical lead" in missing:
        missing.remove("technical lead")
    return _derived("key_roles_missing", missing, f"Derived from the roles of {len(founders)} founder(s)", founders, today)


def total_raised(facts: Facts, today: str) -> Fact | None:
    rounds = [r for r in items(facts, "equity_rounds") if r.value.get("amount") is not None]
    convertible = [r for r in rounds if (r.value.get("currency") or "EUR").upper() in FX_TO_EUR]
    if not convertible:
        return None
    total = sum(r.value["amount"] * FX_TO_EUR[(r.value.get("currency") or "EUR").upper()] for r in convertible)
    skipped = len(rounds) - len(convertible)
    basis = f"Sum of {len(convertible)} equity round(s), approximate FX to EUR" + (f"; {skipped} in unknown currency skipped" if skipped else "")
    return _derived("total_raised", round(total), basis, convertible, today)


def stage(facts: Facts, today: str) -> Fact | None:
    rounds = items(facts, "equity_rounds")
    staged = [r for r in rounds if r.value.get("stage") in ROUND_ORDER]
    if staged:
        latest = max(staged, key=lambda r: ROUND_ORDER.index(r.value["stage"]))
        return _derived("stage", latest.value["stage"], "Most advanced equity round", [latest], today)
    if not rounds and (grants := items(facts, "grants")):
        return _derived("stage", "grant_only", "Grants but no equity rounds found", grants, today)
    return None


def derive_all(facts: Facts, *, website_domain: str, today: str) -> Facts:
    out: Facts = {
        "website_domain": Fact("website_domain", website_domain, f"Input website domain: {website_domain}", "", "manual", today, "inferred", 1.0),
        "key_roles_missing": key_roles_missing(facts, today),
        "total_raised": total_raised(facts, today),
        "stage": stage(facts, today),
    }
    return out


def last_changed(facts: Facts) -> dict[str, str]:
    """Most recent retrieved_at per section."""
    latest: dict[str, str] = {}
    for name, entry in facts.items():
        spec = FIELDS_BY_NAME.get(name)
        dates = [f.retrieved_at for f in (entry if isinstance(entry, list) else [entry]) if f is not None]
        if spec and dates:
            latest[spec.section] = max([latest.get(spec.section, ""), *dates])
    return dict(sorted(latest.items()))
