"""N-hop subgraphs of the knowledge graph, for matching: around one startup, or around an investor thesis.

    startup  seeds: the startup's own entity, else every entity from its documents
    thesis   seeds: the entities LightRAG retrieves for the thesis text (the search's retrieval)

From the seeds a breadth-first walk follows relations for up to ``hops`` steps, keeping at most
``max_nodes`` entities (the best-connected ones of the last level when it doesn't fit). Each entity
records the documents it was extracted from, so the walk reaches startups: a startup scores
sum(1 / (hop + 1)) over its entities in the subgraph, so sharing a seed counts 1 and an entity one
hop out 1/2. Only the graph storage's batch reads are used, so any LightRAG graph storage works.
"""

from __future__ import annotations

from collections import defaultdict
from dataclasses import dataclass
from typing import Any

from .search import SOURCE_SEP, StartupMatch, _group_key, _groups, _matched_terms, _sources

MAX_DESCRIPTION = 300
MAX_HOPS = 3


@dataclass(frozen=True, slots=True)
class GraphNode:
    id: str  # entity name
    type: str | None
    description: str
    hop: int  # steps from the nearest seed
    startups: tuple[str, ...]  # keys of the startups it was extracted from: "startup:<slug>" or "entry:<id>"


@dataclass(frozen=True, slots=True)
class GraphEdge:
    source: str
    target: str
    keywords: str
    description: str
    weight: float


@dataclass(frozen=True, slots=True)
class Subgraph:
    seeds: tuple[str, ...]
    nodes: tuple[GraphNode, ...]  # by hop, then name
    edges: tuple[GraphEdge, ...]
    startups: tuple[StartupMatch, ...]  # startups the subgraph reaches, best first
    truncated: bool  # max_nodes cut the walk short


async def walk(graph: Any, seeds: list[str], *, hops: int, max_nodes: int) -> tuple[dict[str, int], bool]:
    """Entity -> hop for everything within ``hops`` of ``seeds``, at most ``max_nodes`` entities."""
    hop_of: dict[str, int] = {}
    frontier = sorted(set(seeds) & set(await graph.get_nodes_batch(sorted(set(seeds)))))
    for level in range(min(hops, MAX_HOPS) + 1):
        if not frontier:
            return hop_of, False
        room = max_nodes - len(hop_of)
        if len(frontier) > room:
            degrees = await graph.node_degrees_batch(frontier)
            frontier = sorted(frontier, key=lambda n: (-degrees.get(n, 0), n))[:room]
            hop_of.update((n, level) for n in frontier)
            return hop_of, True
        hop_of.update((n, level) for n in frontier)
        if level == hops:
            break
        edges = await graph.get_nodes_edges_batch(frontier)
        frontier = sorted({n for pairs in edges.values() for pair in pairs or () for n in pair if n not in hop_of})
    return hop_of, False


async def subgraph(
    graph: Any,
    documents: dict[str, dict[str, Any]],
    seeds: list[str],
    *,
    hops: int,
    max_nodes: int,
    exclude: str | None = None,
) -> Subgraph:
    """The walk from ``seeds`` with entity details, the relations among them and the startups reached."""
    hop_of, truncated = await walk(graph, seeds, hops=hops, max_nodes=max_nodes)
    names = sorted(hop_of, key=lambda n: (hop_of[n], n))
    details = await graph.get_nodes_batch(names) if names else {}
    nodes = tuple(
        GraphNode(
            id=name,
            type=details.get(name, {}).get("entity_type"),
            description=_short(details.get(name, {}).get("description")),
            hop=hop_of[name],
            startups=tuple(dict.fromkeys(_group_key(d, documents[d]) for d in _sources(details.get(name, {})) if d in documents)),
        )
        for name in names
    )

    pairs = sorted({tuple(sorted(p)) for ps in (await graph.get_nodes_edges_batch(names) if names else {}).values()
                    for p in ps or () if p[0] in hop_of and p[1] in hop_of and p[0] != p[1]})
    found = await graph.get_edges_batch([{"src": a, "tgt": b} for a, b in pairs]) if pairs else {}
    edges = tuple(
        GraphEdge(a, b, str(e.get("keywords") or ""), _short(e.get("description")), float(e.get("weight") or 1.0))
        for (a, b) in pairs
        if (e := found.get((a, b)) or found.get((b, a))) is not None
    )
    return Subgraph(tuple(s for s in dict.fromkeys(seeds) if s in hop_of), nodes, edges, reached(nodes, documents, exclude=exclude), truncated)


def reached(nodes: tuple[GraphNode, ...], documents: dict[str, dict[str, Any]], *, exclude: str | None = None) -> tuple[StartupMatch, ...]:
    """Startups ranked by their entities in the subgraph: each counts 1 / (hop + 1)."""
    groups = _groups(documents)
    scores: dict[str, float] = defaultdict(float)
    terms: dict[str, list[str]] = defaultdict(list)
    for node in nodes:
        for key in node.startups:
            if key != exclude and key in groups:
                scores[key] += 1 / (node.hop + 1)
                terms[key].append(node.id)
    if not scores:
        return ()
    top = max(scores.values())
    ordered = sorted(scores, key=lambda key: (-scores[key], groups[key]["name"].casefold()))
    return tuple(
        StartupMatch(
            slug=groups[key]["slug"],
            entry=groups[key]["entry"],
            name=groups[key]["name"],
            website=groups[key]["website"],
            info=groups[key]["info"],
            relevance=round(scores[key] / top, 3),
            matched=_matched_terms(terms[key], groups[key]["name"]),
            documents=tuple(groups[key]["documents"]),
        )
        for key in ordered
    )


async def startup_seeds(graph: Any, documents: dict[str, dict[str, Any]], key: str) -> list[str]:
    """The startup's own entity if the graph has one, else every entity extracted from its documents."""
    own = {doc_id for doc_id, meta in documents.items() if _group_key(doc_id, meta) == key}
    names = {meta["name"].casefold() for doc_id, meta in documents.items() if doc_id in own}
    entities = [str(n.get("entity_id") or n.get("id")) for n in await graph.get_all_nodes() if own & set(_sources(n))]
    named = [e for e in entities if e.casefold() in names]
    return sorted(named or entities)


def _short(text: Any) -> str:
    text = " ".join(str(text or "").replace(SOURCE_SEP, " ").split())
    return text if len(text) <= MAX_DESCRIPTION else text[: MAX_DESCRIPTION - 1].rstrip() + "…"
