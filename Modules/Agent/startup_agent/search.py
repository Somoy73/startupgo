"""Web search for the research agent, through official search APIs (no search-engine scraping).

Providers:
  gemini  Google Search via Gemini grounding; uses the [llm] Gemini key (default)
  brave   Brave Search API; key in the env var named by [search] api_key_env
  none    no web search; research uses the startup's website and discovery data only

Search only finds URLs. The pages are fetched through the scraper and go through the
same quote-verified extraction as everything else.
"""

from __future__ import annotations

import json
from datetime import date
from collections.abc import Callable
from dataclasses import asdict, dataclass
from typing import Protocol
from urllib.error import HTTPError, URLError
from urllib.parse import urlencode, urlsplit
from urllib.request import Request, urlopen

from .cache import JsonCache
from .errors import AgentError
from .llm import GeminiSession, UsageStats
from .retrievals import Retrieval, RetrievalLog


@dataclass(frozen=True, slots=True)
class SearchHit:
    url: str
    title: str


class WebSearch(Protocol):
    name: str

    @property
    def available(self) -> bool: ...  # False once the provider's quota is exhausted for this run

    def search(self, query: str, *, limit: int) -> list[SearchHit]: ...


class GeminiGoogleSearch:
    """Google Search through Gemini's grounding tool; returns the pages the search grounded on."""

    name = "gemini"
    _PROMPT = "Search the web for: {query}\nList the most relevant pages, one per line."

    def __init__(self, session: GeminiSession, *, model: str, resolve: Callable[[str], str | None]):
        self._session = session
        self.model = model
        self._resolve = resolve

    @property
    def available(self) -> bool:
        return self._session.available("search")

    def search(self, query: str, *, limit: int) -> list[SearchHit]:
        from google.genai import types

        response = self._session.generate(
            model=self.model,
            contents=self._PROMPT.format(query=query),
            kind="search",
            tools=[types.Tool(google_search=types.GoogleSearch())],
            temperature=0,
        )
        metadata = response.candidates[0].grounding_metadata if response.candidates else None
        hits = []
        for chunk in (metadata.grounding_chunks or []) if metadata else []:
            web = chunk.web
            # Grounding links are short-lived redirects; store the real page URL.
            if web and web.uri and (url := self._resolve(web.uri)):
                hits.append(SearchHit(url, web.title or ""))
        return hits[:limit]


class BraveSearch:
    name = "brave"
    _ENDPOINT = "https://api.search.brave.com/res/v1/web/search"

    available = True

    def __init__(self, *, api_key: str, timeout: float = 20):
        self._api_key = api_key
        self._timeout = timeout

    def search(self, query: str, *, limit: int) -> list[SearchHit]:
        request = Request(
            f"{self._ENDPOINT}?{urlencode({'q': query, 'count': limit})}",
            headers={"Accept": "application/json", "X-Subscription-Token": self._api_key},
        )
        try:
            with urlopen(request, timeout=self._timeout) as response:
                data = json.loads(response.read().decode("utf-8"))
        except (HTTPError, URLError, TimeoutError, json.JSONDecodeError) as exc:
            raise AgentError(f"Brave search failed: {exc}") from exc
        results = (data.get("web") or {}).get("results") or []
        return [SearchHit(r["url"], r.get("title", "")) for r in results if r.get("url")][:limit]


class CachedSearch:
    """Caches hits per (provider, query, limit) so reruns repeat no searches."""

    def __init__(self, inner: WebSearch, cache: JsonCache, *, stats: UsageStats | None = None, log: RetrievalLog | None = None):
        self.inner = inner
        self.name = inner.name
        self.cache = cache
        self.stats = stats
        self.log = log

    @property
    def available(self) -> bool:
        return self.inner.available

    def search(self, query: str, *, limit: int) -> list[SearchHit]:
        key = f"{self.name}:{limit}:{query}"
        if (cached := self.cache.get("search", key)) is not None:
            if self.stats:
                self.stats.search_cached += 1
            hits = [SearchHit(**hit) for hit in cached]
            self._record(query, "cached", hits)
            return hits
        try:
            hits = self.inner.search(query, limit=limit)
        except AgentError as exc:
            self._record(query, "error", detail=str(exc))
            raise
        self.cache.put("search", key, [asdict(hit) for hit in hits])
        self._record(query, "ok", hits)
        return hits

    def _record(self, query: str, status: str, hits: list[SearchHit] = (), detail: str | None = None) -> None:
        if self.log is not None:
            self.log.add(Retrieval("search", status, query=query, provider=self.name, retrieved_at=date.today().isoformat(),
                                   detail=detail or json.dumps([asdict(hit) for hit in hits])))


def resolve_redirect(url: str, *, user_agent: str, timeout: float = 15) -> str | None:
    """Final URL after redirects, or None if the redirect itself can't be followed."""
    try:
        with urlopen(Request(url, headers={"User-Agent": user_agent}, method="HEAD"), timeout=timeout) as response:
            return response.geturl()
    except HTTPError as exc:
        # Many sites reject HEAD (e.g. 405) after the redirect resolved; the error still knows the final URL.
        final = exc.geturl()
        return final if final and urlsplit(final).hostname != urlsplit(url).hostname else None
    except (URLError, TimeoutError, ValueError):
        return None
