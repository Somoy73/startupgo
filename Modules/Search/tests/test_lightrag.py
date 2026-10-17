"""The real LightRAG pipeline with fake models: ProcessStorage writes vector + graph storage, StartupSearch reads it."""

import asyncio
from functools import partial

from lightrag.utils import EmbeddingFunc, Tokenizer

from startup_search.process_storage import ProcessStorage
from startup_search.search import StartupSearch
from startup_search.storage import build_rag

from .helpers import CharTokenizer, doc, fake_embed, fake_llm, settings

DOCS = [
    doc("startup:notpla", "# Notpla\nSeaweed packaging that replaces plastic.\n", name="Notpla", startup="notpla", info={"sector": "Packaging"}),
    doc("startup:sofar", "# Sofar Ocean\nOcean data from a network of buoys.\n", name="Sofar Ocean", startup="sofar"),
    doc("entry:kelpco", "# KelpCo\nKelp farming in Namibia.\n", name="KelpCo", entry="kelpco", info={"trl": 4}),
]


def fake_models(**kwargs):
    return partial(
        build_rag,
        llm=fake_llm,
        embedding=EmbeddingFunc(embedding_dim=64, func=fake_embed, max_token_size=8192),
        tokenizer=Tokenizer("chars", CharTokenizer()),
        **kwargs,
    )


def test_process_then_search(tmp_path):
    s = settings(tmp_path)
    process = ProcessStorage(s, rag_factory=fake_models())
    search = StartupSearch(s, rag_factory=fake_models(read_only=True))

    async def scenario():
        assert (await process.run(DOCS)).added == [d.id for d in DOCS]
        files = {p.name for p in s.storage.working_dir.iterdir()}
        assert {"graph_chunk_entity_relation.graphml", "vdb_entities.json", "vdb_chunks.json", "kv_store_full_docs.json"} <= files

        top = (await search.search("seaweed packaging"))[0]
        assert (top.slug, top.name, top.relevance, top.info) == ("notpla", "Notpla", 1.0, {"sector": "Packaging"})
        assert {"Seaweed", "Packaging"} <= set(top.matched)
        kelp = (await search.search("kelp", mode="local"))[0]
        assert (kelp.slug, kelp.entry, kelp.info) == (None, "kelpco", {"trl": 4})

        changed = [*DOCS[:2], doc("entry:kelpco", "# KelpCo\nKelp and seaweed farming.\n", name="KelpCo", entry="kelpco")]
        report = await process.run(changed)
        assert (report.updated, report.unchanged) == (["entry:kelpco"], ["startup:notpla", "startup:sofar"])

        assert (await process.run(DOCS[:1])).removed == ["entry:kelpco", "startup:sofar"]
        matches = await search.search("seaweed packaging buoys")  # the running search reloads the new storage
        assert [m.slug for m in matches] == ["notpla"]
        await search.close()

    asyncio.run(scenario())
