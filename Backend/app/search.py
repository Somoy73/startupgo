"""Search wrapper: the seam between POST /api/search and the RAG / vector search.

The endpoint validates the request and shapes the response; everything in between
(understanding the query, retrieval, ranking) belongs to a SearchWrapper. To connect
the real search, implement the protocol and return it from `get_search_wrapper`.
"""

from dataclasses import dataclass
from typing import Protocol

from .schemas import SearchFilters, StartupSummary


@dataclass(frozen=True)
class SearchResult:
    startups: list[StartupSummary]
    # Filters the search applied, shown as chips in the UI; None if it produced none.
    filters: SearchFilters | None = None
    # Shown next to the results, e.g. "Fell back to keyword matching".
    notice: str | None = None


class SearchWrapper(Protocol):
    def search(self, *, query: str | None, filters: SearchFilters | None) -> SearchResult:
        """Exactly one of `query` (what the user typed) or `filters` (edited chips/dropdowns) is set.

        Return the startups in relevance order; the UI sorts them by the user's chosen column."""
        ...


class NotConnectedSearch:
    """Placeholder until the RAG / vector search is wired in."""

    def search(self, *, query: str | None, filters: SearchFilters | None) -> SearchResult:
        raise NotImplementedError("the RAG / vector search wrapper isn't connected yet")


def get_search_wrapper() -> SearchWrapper:
    """FastAPI dependency; tests override it with a fake."""
    return NotConnectedSearch()
