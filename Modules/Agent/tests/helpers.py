"""Test doubles and builders."""

from __future__ import annotations

import re
from typing import Any

from startup_agent.facts import Fact


def fact(field: str, value: Any, *, status: str = "claimed", confidence: float = 0.7, source_type: str = "website") -> Fact:
    return Fact(field, value, f"quote for {field}", "https://acme.fi/", source_type, "2026-10-17", status, confidence)


class FakeLLM:
    """Canned responses keyed by section ("Extract section X:" / "Extract section A, B:") or "judge".

    A response may be a dict, a list (one per call; the last repeats) or a callable(user) -> dict.
    Grouped prompts get the merged responses of their sections.
    """

    model = "fake"

    def __init__(self, responses: dict[str, Any]):
        self.responses = responses
        self.calls: list[dict[str, Any]] = []

    def complete_json(self, *, system: str, user: str, schema: dict[str, Any]) -> dict[str, Any]:
        match = re.search(r"Extract section ([A-J](?:, [A-J])*):", user)
        keys = match.group(1).split(", ") if match else ["judge"]
        self.calls.append({"section": ", ".join(keys), "sections": keys, "user": user, "schema": schema})
        merged: dict[str, Any] = {}
        for key in keys:
            merged.update(self._response(key, user))
        return merged

    def _response(self, key: str, user: str) -> dict[str, Any]:
        response = self.responses.get(key, {})
        if isinstance(response, list):
            response = response[min(self.count(key), len(response)) - 1]
        return response(user) if callable(response) else response

    def count(self, key: str) -> int:
        """Calls that included ``key`` (a section id or "judge")."""
        return sum(1 for call in self.calls if key in call["sections"])


def scalar(value: Any, evidence: str | None, url: str | None = "https://acme.fi/") -> dict[str, Any]:
    return {"value": value, "evidence": evidence, "source_url": url}


def item(value: dict[str, Any], evidence: str, url: str = "https://acme.fi/") -> dict[str, Any]:
    return {"item": value, "evidence": evidence, "source_url": url}
