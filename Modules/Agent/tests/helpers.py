"""Test doubles and builders."""

from __future__ import annotations

import re
from typing import Any

from startup_agent.facts import Fact


def fact(field: str, value: Any, *, status: str = "claimed", confidence: float = 0.7, source_type: str = "website") -> Fact:
    return Fact(field, value, f"quote for {field}", "https://acme.fi/", source_type, "2026-10-17", status, confidence)


class FakeLLM:
    """Returns a canned response per section, parsed from 'Extract section X:' in the prompt."""

    model = "fake"

    def __init__(self, responses: dict[str, dict[str, Any]]):
        self.responses = responses
        self.calls: list[dict[str, Any]] = []

    def complete_json(self, *, system: str, user: str, schema: dict[str, Any]) -> dict[str, Any]:
        section = re.search(r"Extract section ([A-J]):", user).group(1)
        self.calls.append({"section": section, "user": user, "schema": schema})
        return self.responses.get(section, {})


def scalar(value: Any, evidence: str | None, url: str | None = "https://acme.fi/") -> dict[str, Any]:
    return {"value": value, "evidence": evidence, "source_url": url}


def item(value: dict[str, Any], evidence: str, url: str = "https://acme.fi/") -> dict[str, Any]:
    return {"item": value, "evidence": evidence, "source_url": url}
