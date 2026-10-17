"""StartupSearch: a query in, matched startups out, ranked from LightRAG's retrieval."""

import asyncio
import os

import pytest

from startup_search.errors import SearchError, SearchUnavailable
from startup_search.process_storage import ProcessStorage
from startup_search.search import StartupSearch, rank

from .helpers import FakeRag, doc, settings


def item(file_path, **fields):
    return {"file_path": file_path, **fields}


DOCUMENTS = {
    "startup:notpla": {"name": "Notpla", "website": "https://notpla.com", "startup": "notpla", "entry": None, "info": {"sector": "Packaging"}},
    "entry:notpla-com": {"name": "Notpla Ltd", "website": "https://notpla.com", "startup": "notpla", "entry": "notpla-com", "info": {"trl": 8}},
    "startup:sofar": {"name": "Sofar Ocean", "website": None, "startup": "sofar", "entry": None, "info": {}},
    "entry:kelpco": {"name": "KelpCo", "website": "https://kelp.co", "startup": None, "entry": "kelpco", "info": {"trl": 4}},
}


class TestRank:
    def test_documents_about_one_startup_count_together(self):
        data = {
            "entities": [
                item("entry:notpla-com", entity_name="Seaweed"),
                item("entry:kelpco<SEP>startup:notpla", entity_name="Kelp"),
                item("startup:notpla", entity_name="Notpla"),
            ],
            "chunks": [item("startup:notpla"), item("entry:kelpco")],
        }
        notpla, kelpco = rank(data, DOCUMENTS)
        assert (notpla.slug, notpla.entry, notpla.name, notpla.relevance) == ("notpla", "notpla-com", "Notpla", 1.0)  # the database row's name
        assert notpla.info == {"sector": "Packaging", "trl": 8}
        assert notpla.documents == ("startup:notpla", "entry:notpla-com")
        assert notpla.matched == ("Seaweed", "Kelp")  # its own name isn't a match term
        assert (kelpco.slug, kelpco.entry, kelpco.info) == (None, "kelpco", {"trl": 4}) and 0 < kelpco.relevance < 1

    def test_matches_are_database_entities_by_key(self):
        documents = {
            "startup:notpla": {"key": "startup:notpla", "kind": "startup", "name": "Notpla", "startup": "notpla", "entry": None, "info": {}},
            "entry:notpla-com": {"key": "startup:notpla", "kind": "startup", "name": "Notpla Ltd", "startup": "notpla", "entry": "notpla-com", "info": {}},
            "blueinvest:84": {"key": "blueinvest:84", "kind": "candidate", "name": "Skizo", "startup": None, "entry": None, "info": {}},
            "entry:kelpco": {"key": "entry:kelpco", "kind": "entry", "name": "KelpCo", "startup": None, "entry": "kelpco", "info": {}},
        }
        data = {"chunks": [item("entry:notpla-com"), item("blueinvest:84"), item("entry:kelpco")]}
        found = [(m.key, m.kind, m.slug, m.entry) for m in rank(data, documents)]
        assert found == [
            ("startup:notpla", "startup", "notpla", "notpla-com"),
            ("blueinvest:84", "candidate", None, None),
            ("entry:kelpco", "entry", None, "kelpco"),
        ]

    def test_manifests_from_before_entity_keys_still_group_by_startup(self):
        notpla, kelpco = rank({"chunks": [item("entry:notpla-com"), item("entry:kelpco")]}, DOCUMENTS)
        assert (notpla.key, notpla.kind, kelpco.key, kelpco.kind) == ("startup:notpla", "startup", "entry:kelpco", "entry")

    def test_a_long_document_does_not_win_by_size(self):
        many = [item("startup:sofar", entity_name=f"Topic {i}") for i in range(1, 12)]
        data = {"entities": [item("startup:notpla", entity_name="Seaweed"), *many], "chunks": [item("startup:notpla"), item("startup:sofar")]}
        assert [m.slug for m in rank(data, DOCUMENTS)] == ["notpla", "sofar"]

    def test_unknown_sources_are_ignored(self):
        assert rank({"chunks": [item("unknown_source"), item("")]}, DOCUMENTS) == []


RESPONSE = {"status": "success", "data": {"chunks": [item("startup:sofar")]}, "metadata": {}}


def processed(tmp_path, rag):
    """Settings whose storage has Sofar Ocean processed into it."""
    s = settings(tmp_path)
    asyncio.run(ProcessStorage(s, rag_factory=lambda _: rag).run([doc("startup:sofar", "buoys", name="Sofar Ocean", startup="sofar")]))
    return s


def run_search(search, query, **kwargs):
    return asyncio.run(search.search(query, **kwargs))


class TestStartupSearch:
    def test_query_in_matches_out(self, tmp_path):
        rag = FakeRag(RESPONSE)
        search = StartupSearch(processed(tmp_path, rag), rag_factory=lambda _: rag)
        matches = run_search(search, "  buoys \n for ocean data  ")
        assert [(m.slug, m.name) for m in matches] == [("sofar", "Sofar Ocean")]
        query, param = rag.queries[0]
        assert query == "buoys for ocean data"
        assert (param.mode, param.top_k, param.chunk_top_k, param.enable_rerank) == ("mix", 40, 20, False)

    def test_repeated_queries_are_answered_from_memory(self, tmp_path):
        rag = FakeRag(RESPONSE)
        search = StartupSearch(processed(tmp_path, rag), rag_factory=lambda _: rag)
        first = asyncio.run(self.twice(search, "buoys"))
        assert first[0] == first[1] and len(rag.queries) == 1

    async def twice(self, search, query):
        return [await search.search(query), await search.search(query)]

    def test_new_storage_from_process_storage_is_picked_up(self, tmp_path):
        rag = FakeRag(RESPONSE)
        s = processed(tmp_path, rag)
        opened = []

        def factory(_):
            opened.append(1)
            return rag

        search = StartupSearch(s, rag_factory=factory)

        async def scenario():
            await search.search("buoys")
            manifest = s.storage.working_dir / "startupgo_documents.json"
            stat = manifest.stat()
            os.utime(manifest, (stat.st_atime, stat.st_mtime + 5))  # process-storage wrote a new one
            await search.search("buoys")

        asyncio.run(scenario())
        assert len(opened) == 2 and len(rag.queries) == 2  # reopened, and the cached answer dropped

    def test_nothing_processed_means_unavailable(self, tmp_path):
        search = StartupSearch(settings(tmp_path), rag_factory=lambda _: FakeRag())
        with pytest.raises(SearchUnavailable, match="process-storage"):
            run_search(search, "kelp")

    def test_missing_key_means_unavailable(self, tmp_path):
        with pytest.raises(SearchUnavailable, match="CHAT_API_KEY"):
            run_search(StartupSearch(settings(tmp_path)), "kelp")

    @pytest.mark.parametrize("response", [{"status": "failure", "message": "rate limited"}, RuntimeError("rate limited")])
    def test_lightrag_failures_are_search_errors(self, tmp_path, response):
        rag = FakeRag()
        s = processed(tmp_path, rag)
        rag.response = response
        with pytest.raises(SearchError, match="rate limited"):
            run_search(StartupSearch(s, rag_factory=lambda _: rag), "kelp")

    def test_empty_query(self, tmp_path):
        with pytest.raises(SearchError, match="empty"):
            run_search(StartupSearch(settings(tmp_path), rag_factory=lambda _: FakeRag()), "   ")
