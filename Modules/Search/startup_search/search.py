"""The search interface for the Backend: a user query in, matched startups out.

    search = StartupSearch()                                   # settings from Search/config.toml
    matches = await search.search("seaweed packaging startups")  # list[StartupMatch], best first
    await search.close()                                       # on shutdown

The storage is opened on the first search (so the Backend starts without a key or an index) and
reopened when ProcessStorage has written a new one.

Search uses LightRAG's retrieval only (``aquery_data``), not its answer generation: the chat model
picks keywords from the query, then entities, relations and text chunks are retrieved from the
knowledge graph and the vector store. A startup scores by its best position in each of the three
lists (reciprocal-rank fusion); its documents (database row, agent entry) count together.
"""

from __future__ import annotations

import asyncio
from collections import defaultdict
from collections.abc import Callable
from dataclasses import dataclass
from functools import partial
from typing import Any

from .config import SearchSettings
from .errors import SearchError, SearchUnavailable
from .storage import Manifest, Rag, build_rag

RRF_K = 10  # lists are short (top_k items): first place counts 1/11, tenth 1/20, thirtieth 1/40
MAX_MATCHED = 5
SOURCE_SEP = "<SEP>"  # how LightRAG joins the file paths of merged entities (lightrag.constants.GRAPH_FIELD_SEP)
CACHED_QUERIES = 256


@dataclass(frozen=True, slots=True)
class StartupMatch:
    """A startup the search found, with the info stored when its documents were processed."""

    slug: str | None  # StartupGo database slug; None if only an agent entry knows the startup
    entry: str | None  # agent entry id, if there is one
    name: str
    website: str | None
    info: dict[str, Any]  # database: tagline, sector, country, city, stage; agent entry: its scores
    relevance: float  # 0-1, relative to the best match
    matched: tuple[str, ...]  # knowledge-graph entities that led here, most relevant first
    documents: tuple[str, ...]  # the matched documents, e.g. ("startup:notpla", "entry:notpla-com")


class StartupSearch:
    def __init__(
        self,
        settings: SearchSettings | None = None,
        *,
        rag_factory: Callable[[SearchSettings], Rag] = partial(build_rag, read_only=True),
    ):
        self._settings = settings
        self._rag_factory = rag_factory
        self._rag: Rag | None = None
        self._documents: dict[str, dict[str, Any]] = {}
        self._loaded: float | None = None  # manifest time of the open storage
        self._lock: asyncio.Lock | None = None
        self._cache: dict[tuple[str, str], list[StartupMatch]] = {}

    @property
    def settings(self) -> SearchSettings:
        if self._settings is None:
            self._settings = SearchSettings.load()
        return self._settings

    async def search(self, query: str, *, limit: int | None = None, mode: str | None = None) -> list[StartupMatch]:
        """Startups matching ``query``, best first (at most ``limit``, default [query] max_results)."""
        from lightrag import QueryParam

        query = " ".join(query.split())
        if not query:
            raise SearchError("empty search query")
        rag = await self._open()
        if not self._documents:
            raise SearchUnavailable("nothing has been processed yet: run process-storage")
        settings = self.settings.query
        mode = mode or settings.mode
        limit = limit or settings.max_results
        if (query, mode) in self._cache:
            return self._cache[query, mode][:limit]

        param = QueryParam(mode=mode, top_k=settings.top_k, chunk_top_k=settings.chunk_top_k, enable_rerank=False)
        try:
            response = await rag.aquery_data(query, param)
        except Exception as exc:  # model, network and storage errors from LightRAG's layers
            raise SearchError(f"search failed: {exc}") from exc
        if response.get("status") != "success":
            raise SearchError(f"search failed: {response.get('message') or 'unknown error'}")

        matches = rank(response.get("data") or {}, self._documents)
        if len(self._cache) >= CACHED_QUERIES:
            self._cache.pop(next(iter(self._cache)))
        self._cache[query, mode] = matches
        return matches[:limit]

    async def close(self) -> None:
        if self._rag is not None:
            rag, self._rag = self._rag, None
            await rag.finalize_storages()

    async def _open(self) -> Rag:
        self._lock = self._lock or asyncio.Lock()
        async with self._lock:
            manifest = Manifest(self.settings)
            modified = manifest.modified()
            if self._rag is None or modified != self._loaded:  # first search, or new storage processed
                await self.close()
                rag = self._rag_factory(self.settings)
                await rag.initialize_storages()
                self._rag, self._documents, self._loaded = rag, manifest.load().documents, modified
                self._cache.clear()
            return self._rag


def rank(data: dict[str, Any], documents: dict[str, dict[str, Any]]) -> list[StartupMatch]:
    """Fuse LightRAG's entity, relation and chunk rankings into one ranking of startups.

    Only a startup's best position in each list counts, so long documents (which yield many
    entities) don't outrank short ones just by size.
    """
    groups = _groups(documents)
    scores: dict[str, float] = defaultdict(float)
    matched: dict[str, list[str]] = defaultdict(list)
    for kind in ("entities", "relationships", "chunks"):
        best: dict[str, int] = {}
        for position, item in enumerate(data.get(kind) or []):
            for key in {_group_key(doc_id, documents[doc_id]) for doc_id in _sources(item) if doc_id in documents}:
                best.setdefault(key, position)
                if kind == "entities" and item.get("entity_name"):
                    matched[key].append(str(item["entity_name"]))
        for key, position in best.items():
            scores[key] += 1 / (RRF_K + position + 1)
    if not scores:
        return []
    top = max(scores.values())
    ordered = sorted(scores, key=lambda key: (-scores[key], groups[key]["name"].casefold()))
    return [
        StartupMatch(
            slug=groups[key]["slug"],
            entry=groups[key]["entry"],
            name=groups[key]["name"],
            website=groups[key]["website"],
            info=groups[key]["info"],
            relevance=round(scores[key] / top, 3),
            matched=_matched_terms(matched[key], groups[key]["name"]),
            documents=tuple(groups[key]["documents"]),
        )
        for key in ordered
    ]


def _groups(documents: dict[str, dict[str, Any]]) -> dict[str, dict[str, Any]]:
    """One group per startup: the database row's name and website win over an agent entry's."""
    groups: dict[str, dict[str, Any]] = {}
    for doc_id, meta in sorted(documents.items(), key=lambda item: item[1].get("entry") is not None):
        group = groups.setdefault(
            _group_key(doc_id, meta),
            {"slug": meta.get("startup"), "entry": None, "name": meta["name"], "website": meta.get("website"), "info": {}, "documents": []},
        )
        group["documents"].append(doc_id)
        group["info"] = {**(meta.get("info") or {}), **group["info"]}
        if meta.get("entry") and group["entry"] is None:
            group["entry"] = meta["entry"]
    return groups


def _group_key(doc_id: str, meta: dict[str, Any]) -> str:
    return f"startup:{meta['startup']}" if meta.get("startup") else doc_id


def _sources(item: dict[str, Any]) -> list[str]:
    return [part.strip() for part in str(item.get("file_path") or "").split(SOURCE_SEP) if part.strip()]


def _matched_terms(names: list[str], startup_name: str) -> tuple[str, ...]:
    own = startup_name.casefold()
    unique = dict.fromkeys(n for n in names if n.casefold() != own)
    return tuple(list(unique)[:MAX_MATCHED])
