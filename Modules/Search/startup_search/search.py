"""The search interface for the Backend: a user query in, matched startups out.

    search = StartupSearch()                                   # settings from Search/config.toml
    matches = await search.search("seaweed packaging startups")  # list[StartupMatch], best first
    graph = await search.startup_graph("notpla", hops=2)       # Subgraph: entities, relations, startups reached
    graph = await search.thesis_graph("kelp carbon removal")   # same, seeded by what the thesis retrieves
    await search.close()                                       # on shutdown

The storage is opened on the first search (so the Backend starts without a key or an index) and
reopened when ProcessStorage has written a new one.

Search uses LightRAG's retrieval only (``aquery_data``), not its answer generation: the chat model
picks keywords from the query, then entities, relations and text chunks are retrieved from the
knowledge graph and the vector store. A startup scores by its best position in each of the three
lists (reciprocal-rank fusion); its documents (database entity, agent entry) count together.

A match is a database entity (``key`` "startup:notpla", ``kind`` "startup"; other kinds such as
"candidate" when [sources] kinds indexes them) or an agent entry no database entity has (``kind`` "entry").
"""

from __future__ import annotations

import asyncio
from collections import defaultdict
from collections.abc import Callable
from dataclasses import dataclass
from functools import partial
from typing import TYPE_CHECKING, Any

from .config import SearchSettings
from .errors import SearchError, SearchUnavailable
from .storage import Manifest, Rag, build_rag

if TYPE_CHECKING:
    from .graph import Subgraph

RRF_K = 10  # lists are short (top_k items): first place counts 1/11, tenth 1/20, thirtieth 1/40
MAX_MATCHED = 5
SOURCE_SEP = "<SEP>"  # how LightRAG joins the file paths of merged entities (lightrag.constants.GRAPH_FIELD_SEP)
CACHED_QUERIES = 256


@dataclass(frozen=True, slots=True)
class StartupMatch:
    """A startup the search found, with the info stored when its documents were processed."""

    key: str  # database entity key ("startup:notpla", "blueinvest:84"), or "entry:<id>" for an agent-only startup
    kind: str  # entity kind: "startup", "candidate", ...; "entry" if only an agent entry knows it
    slug: str | None  # StartupGo startup slug (kind "startup"); None otherwise
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
        query = " ".join(query.split())
        if not query:
            raise SearchError("empty search query")
        await self._open_processed()
        mode = mode or self.settings.query.mode
        limit = limit or self.settings.query.max_results
        if (query, mode) in self._cache:
            return self._cache[query, mode][:limit]

        matches = rank(await self._retrieve(query, mode), self._documents)
        if len(self._cache) >= CACHED_QUERIES:
            self._cache.pop(next(iter(self._cache)))
        self._cache[query, mode] = matches
        return matches[:limit]

    async def startup_graph(self, slug: str, *, hops: int = 2, max_nodes: int = 150) -> Subgraph:
        """The knowledge graph within ``hops`` of a database startup, and the other startups it reaches."""
        from .graph import startup_seeds, subgraph

        rag = await self._open_processed()
        key = f"startup:{slug}"
        seeds = await startup_seeds(rag.chunk_entity_relation_graph, self._documents, key)
        if not seeds:
            raise SearchUnavailable(f"{slug} has not been processed yet: run process-storage")
        return await subgraph(rag.chunk_entity_relation_graph, self._documents, seeds, hops=hops, max_nodes=max_nodes, exclude=key)

    async def thesis_graph(self, thesis: str, *, hops: int = 1, max_nodes: int = 150, seeds: int = 10) -> Subgraph:
        """The knowledge graph within ``hops`` of the entities retrieved for ``thesis``, and the startups it reaches."""
        from .graph import subgraph

        thesis = " ".join(thesis.split())
        if not thesis:
            raise SearchError("empty thesis")
        rag = await self._open_processed()
        data = await self._retrieve(thesis, self.settings.query.mode)
        entities = list(dict.fromkeys(str(e["entity_name"]) for e in data.get("entities") or [] if e.get("entity_name")))
        return await subgraph(rag.chunk_entity_relation_graph, self._documents, entities[:seeds], hops=hops, max_nodes=max_nodes)

    async def _open_processed(self) -> Rag:
        rag = await self._open()
        if not self._documents:
            raise SearchUnavailable("nothing has been processed yet: run process-storage")
        return rag

    async def _retrieve(self, query: str, mode: str) -> dict[str, Any]:
        """LightRAG's retrieval for ``query``: its entities, relationships and chunks, best first."""
        from lightrag import QueryParam

        settings = self.settings.query
        param = QueryParam(mode=mode, top_k=settings.top_k, chunk_top_k=settings.chunk_top_k, enable_rerank=False)
        try:
            response = await self._rag.aquery_data(query, param)
        except Exception as exc:  # model, network and storage errors from LightRAG's layers
            raise SearchError(f"search failed: {exc}") from exc
        if response.get("status") != "success":
            raise SearchError(f"search failed: {response.get('message') or 'unknown error'}")
        return response.get("data") or {}

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
    return [_match(key, groups[key], scores[key] / top, matched[key]) for key in ordered]


def _match(key: str, group: dict[str, Any], relevance: float, terms: list[str]) -> StartupMatch:
    return StartupMatch(
        key=key,
        kind=group["kind"],
        slug=group["slug"],
        entry=group["entry"],
        name=group["name"],
        website=group["website"],
        info=group["info"],
        relevance=round(relevance, 3),
        matched=_matched_terms(terms, group["name"]),
        documents=tuple(group["documents"]),
    )


def _groups(documents: dict[str, dict[str, Any]]) -> dict[str, dict[str, Any]]:
    """One group per entity: the database entity's name and website win over an agent entry's."""
    groups: dict[str, dict[str, Any]] = {}
    for doc_id, meta in sorted(documents.items(), key=lambda item: item[1].get("entry") is not None):
        group = groups.setdefault(
            _group_key(doc_id, meta),
            {
                "kind": meta.get("kind") or ("startup" if meta.get("startup") else "entry"),
                "slug": meta.get("startup"),
                "entry": None,
                "name": meta["name"],
                "website": meta.get("website"),
                "info": {},
                "documents": [],
            },
        )
        group["documents"].append(doc_id)
        group["info"] = {**(meta.get("info") or {}), **group["info"]}
        if meta.get("entry") and group["entry"] is None:
            group["entry"] = meta["entry"]
    return groups


def _group_key(doc_id: str, meta: dict[str, Any]) -> str:
    """The entity a document is about; manifests from before entity keys fall back to the startup slug."""
    return meta.get("key") or (f"startup:{meta['startup']}" if meta.get("startup") else doc_id)


def _sources(item: dict[str, Any]) -> list[str]:
    return [part.strip() for part in str(item.get("file_path") or "").split(SOURCE_SEP) if part.strip()]


def _matched_terms(names: list[str], startup_name: str) -> tuple[str, ...]:
    own = startup_name.casefold()
    unique = dict.fromkeys(n for n in names if n.casefold() != own)
    return tuple(list(unique)[:MAX_MATCHED])
