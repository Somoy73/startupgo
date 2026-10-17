"""N-hop subgraphs for matching: the walk itself, and the real LightRAG storage with fake models."""

import asyncio

import pytest

from startup_search.errors import SearchUnavailable
from startup_search.graph import walk
from startup_search.process_storage import ProcessStorage
from startup_search.search import StartupSearch

from .helpers import doc, settings
from .test_lightrag import fake_models

DOCS = [
    doc("startup:notpla", "# Notpla\nSeaweed packaging that replaces plastic.\n", name="Notpla", startup="notpla"),
    doc("startup:oceanium", "# Oceanium\nSeaweed biorefinery.\n", name="Oceanium", startup="oceanium"),
    doc("startup:sofar", "# Sofar Ocean\nOcean data from a network of buoys.\n", name="Sofar Ocean", startup="sofar"),
    doc("entry:kelpco", "# KelpCo\nKelp farming in Namibia.\n", name="KelpCo", entry="kelpco"),
]


class FakeGraph:
    """A star: hub linked to a, b, c; a linked to d."""

    EDGES = [("hub", "a"), ("hub", "b"), ("hub", "c"), ("a", "d")]

    async def get_nodes_batch(self, ids):
        return {i: {"entity_id": i} for i in ids if i in {"hub", "a", "b", "c", "d"}}

    async def get_nodes_edges_batch(self, ids):
        return {i: [e for e in self.EDGES if i in e] for i in ids}

    async def node_degrees_batch(self, ids):
        return {i: sum(i in e for e in self.EDGES) for i in ids}


def test_walk_counts_hops_and_keeps_the_best_connected_nodes_when_truncated():
    graph = FakeGraph()
    assert asyncio.run(walk(graph, ["hub", "missing"], hops=2, max_nodes=10)) == ({"hub": 0, "a": 1, "b": 1, "c": 1, "d": 2}, False)
    assert asyncio.run(walk(graph, ["hub"], hops=0, max_nodes=10)) == ({"hub": 0}, False)
    assert asyncio.run(walk(graph, ["hub"], hops=2, max_nodes=2)) == ({"hub": 0, "a": 1}, True)  # a has degree 2


def test_startup_and_thesis_graphs_on_processed_storage(tmp_path):
    s = settings(tmp_path)
    search = StartupSearch(s, rag_factory=fake_models(read_only=True))

    async def scenario():
        with pytest.raises(SearchUnavailable):
            await search.startup_graph("notpla")
        await ProcessStorage(s, rag_factory=fake_models()).run(DOCS)

        g = await search.startup_graph("notpla", hops=2)
        assert g.seeds == ("Notpla",)
        hops = {n.id: n.hop for n in g.nodes}
        assert hops["Notpla"] == 0 and hops["Seaweed"] == 1 and hops["Oceanium"] == 2
        assert "Sofar Ocean" not in hops
        seaweed = next(n for n in g.nodes if n.id == "Seaweed")
        assert set(seaweed.startups) == {"startup:notpla", "startup:oceanium"}
        assert ("Notpla", "Seaweed") in {(e.source, e.target) for e in g.edges}
        assert [m.slug for m in g.startups] == ["oceanium"]  # notpla itself is left out
        assert "Seaweed" in g.startups[0].matched

        with pytest.raises(SearchUnavailable):
            await search.startup_graph("unknown")

        t = await search.thesis_graph("kelp", hops=1)
        assert "Kelp" in t.seeds
        assert t.startups[0].entry == "kelpco"
        await search.close()

    asyncio.run(scenario())
