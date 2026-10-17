"""Errors raised by the search package."""


class SearchError(RuntimeError):
    """A search or indexing step failed (bad settings, model or storage error)."""


class SearchUnavailable(SearchError):
    """Search can't run yet: no API key, or nothing has been indexed."""
