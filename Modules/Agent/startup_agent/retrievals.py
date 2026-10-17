"""What the agent looked at during one research run: every page loaded and web search made, in order.

The page loader and the search wrapper add to a shared log; the pipeline stores it in the agent_runs and
agent_retrievals tables (database.py) when the run ends and starts a fresh one for the next candidate.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Literal

Kind = Literal["page", "search"]
Status = Literal["ok", "error", "skipped", "cached"]


@dataclass(frozen=True, slots=True)
class Retrieval:
    kind: Kind
    status: Status
    url: str | None = None
    query: str | None = None
    provider: str | None = None
    source_type: str | None = None
    detail: str | None = None  # error message, skip reason, or JSON list of search hits
    retrieved_at: str = ""


@dataclass(slots=True)
class RetrievalLog:
    items: list[Retrieval] = field(default_factory=list)

    def add(self, item: Retrieval) -> None:
        self.items.append(item)

    def drain(self) -> list[Retrieval]:
        items, self.items = self.items, []
        return items
