"""ProcessStorage keeps LightRAG's storage in step with the database: only new and changed startups cost model calls."""

import asyncio
import json

import pytest

from startup_search.errors import SearchError
from startup_search.process_storage import ProcessStorage

from .helpers import FakeRag, doc, settings


def process(tmp_path, rag, documents, **kwargs):
    return asyncio.run(ProcessStorage(settings(tmp_path), rag_factory=lambda _: rag).run(documents, **kwargs))


def manifest(tmp_path):
    return json.loads((tmp_path / "rag" / "startupgo_documents.json").read_text())["documents"]


def test_new_documents_are_inserted_with_their_id_as_file_path(tmp_path):
    rag = FakeRag()
    report = process(tmp_path, rag, [doc("startup:notpla", "a", startup="notpla", info={"sector": "Packaging"}), doc("entry:kelpco", "b", entry="kelpco")])
    assert report.added == ["startup:notpla", "entry:kelpco"]
    assert rag.inserted == [["startup:notpla", "entry:kelpco"]] and rag.file_paths == rag.inserted
    saved = manifest(tmp_path)
    assert saved["startup:notpla"]["startup"] == "notpla" and saved["startup:notpla"]["info"] == {"sector": "Packaging"}
    assert saved["entry:kelpco"]["entry"] == "kelpco"


def test_only_changed_documents_are_processed_again(tmp_path):
    rag = FakeRag()
    process(tmp_path, rag, [doc("startup:a", "one"), doc("startup:b", "two")])
    report = process(tmp_path, rag, [doc("startup:a", "one"), doc("startup:b", "two, changed")])
    assert (report.unchanged, report.updated) == (["startup:a"], ["startup:b"])
    assert rag.deleted == ["startup:b"]  # LightRAG skips ids it already has, so the old copy goes first
    assert rag.inserted[-1] == ["startup:b"]


def test_a_new_link_or_info_needs_no_processing(tmp_path):
    rag = FakeRag()
    process(tmp_path, rag, [doc("entry:kelpco", "text", entry="kelpco")])
    report = process(tmp_path, rag, [doc("entry:kelpco", "text", entry="kelpco", startup="kelp-co")])  # now in the database
    assert report.unchanged == ["entry:kelpco"] and len(rag.inserted) == 1
    assert manifest(tmp_path)["entry:kelpco"]["startup"] == "kelp-co"


def test_startups_that_left_the_database_are_removed_unless_kept(tmp_path):
    rag = FakeRag()
    process(tmp_path, rag, [doc("startup:a", "one"), doc("startup:b", "two")])
    assert process(tmp_path, rag, [doc("startup:a", "one")], prune=False).removed == []
    report = process(tmp_path, rag, [doc("startup:a", "one")])
    assert report.removed == ["startup:b"] and rag.deleted == ["startup:b"] and "startup:b" not in manifest(tmp_path)


def test_failed_documents_are_reported_and_retried(tmp_path):
    rag = FakeRag(fail={"startup:b"})
    report = process(tmp_path, rag, [doc("startup:a", "one"), doc("startup:b", "two")])
    assert report.added == ["startup:a"] and report.failed == {"startup:b": "model timeout"}
    assert "startup:b" not in manifest(tmp_path)

    rag.fail.clear()
    report = process(tmp_path, rag, [doc("startup:a", "one"), doc("startup:b", "two")])
    assert report.added == ["startup:b"] and rag.deleted == ["startup:b"]  # the failed copy is removed first


def test_duplicate_ids_are_rejected(tmp_path):
    with pytest.raises(SearchError, match="unique"):
        process(tmp_path, FakeRag(), [doc("startup:a", "one"), doc("startup:a", "two")])


def test_documents_come_from_the_configured_database(tmp_path):
    with pytest.raises(SearchError, match="database not found"):
        ProcessStorage(settings(tmp_path, '[sources]\ndatabase = "missing.db"\n')).documents()
