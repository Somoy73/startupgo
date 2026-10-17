"""ProcessStorage: turns the StartupGo database (and the agent's entries) into LightRAG's storage.

    database rows / agent entries -> one text document per startup (documents.py)
      -> chunks -> entities and relations, extracted by the chat model -> knowledge graph (GraphDB)
      -> embeddings of chunks, entities and relations                  -> vector store (VectorDB)

Run it after the database changes (from Modules/Search):

    uv run process-storage                         # everything new or changed
    uv run process-storage --limit 20 --pause 5    # only the top 20 still to process, 5 s apart

Only new and changed documents are processed (each costs a few chat-model calls), one at a time and
best first (documents.py ranks them), and each is saved as soon as it is done: an interrupted or
limited run keeps what it finished, and the next run goes on with the rest. Entities that left the
database are removed. A running search loads the new storage on its next query.
"""

from __future__ import annotations

import argparse
import asyncio
import logging
import sys
import time
from collections.abc import Callable, Sequence
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

from .config import SearchSettings
from .documents import Document, load_documents
from .errors import SearchError
from .storage import Manifest, Rag, build_rag


@dataclass
class ProcessReport:
    added: list[str] = field(default_factory=list)
    updated: list[str] = field(default_factory=list)
    removed: list[str] = field(default_factory=list)
    unchanged: list[str] = field(default_factory=list)
    failed: dict[str, str] = field(default_factory=dict)  # document id -> error
    waiting: list[str] = field(default_factory=list)  # new or changed, left for a later run by ``limit``

    def summary(self) -> str:
        counts = [
            f"{len(ids)} {label}"
            for label, ids in (
                ("added", self.added),
                ("updated", self.updated),
                ("removed", self.removed),
                ("unchanged", self.unchanged),
                ("failed", self.failed),
                ("waiting", self.waiting),
            )
            if ids
        ]
        return ", ".join(counts) or "nothing to process"


class ProcessStorage:
    def __init__(self, settings: SearchSettings | None = None, *, rag_factory: Callable[[SearchSettings], Rag] = build_rag):
        self.settings = settings or SearchSettings.load()
        self.rag_factory = rag_factory

    def documents(self) -> list[Document]:
        """What would be processed: every database startup and agent entry (no model calls)."""
        return load_documents(self.settings.database, self.settings.entries, self.settings.kinds)

    async def run(
        self,
        documents: list[Document] | None = None,
        *,
        prune: bool = True,
        limit: int | None = None,
        pause: float = 0.0,
        progress: Callable[[str, str], None] | None = None,
    ) -> ProcessReport:
        """Bring the storage in line with ``documents`` (default: the database and agent entries, best first).

        At most ``limit`` new or changed documents are processed, in the given order, ``pause`` seconds
        apart; ``progress(doc_id, outcome)`` is told about each one.
        """
        documents = self.documents() if documents is None else documents
        if len({doc.id for doc in documents}) != len(documents):
            raise SearchError("document ids must be unique")
        manifest = Manifest(self.settings).load()
        rag = self.rag_factory(self.settings)
        await rag.initialize_storages()
        try:
            return await _process(rag, manifest, documents, prune=prune, limit=limit, pause=pause, progress=progress)
        finally:
            await rag.finalize_storages()
            manifest.save()


async def _process(
    rag: Rag,
    manifest: Manifest,
    documents: list[Document],
    *,
    prune: bool,
    limit: int | None,
    pause: float,
    progress: Callable[[str, str], None] | None,
) -> ProcessReport:
    report = ProcessReport()
    indexed = manifest.documents
    wanted = {doc.id for doc in documents}
    statuses = await rag.aget_docs_by_ids(sorted(wanted | set(indexed)))

    if prune:
        for doc_id in sorted(set(indexed) - wanted):
            await _delete(rag, doc_id)
            del indexed[doc_id]
            report.removed.append(doc_id)

    todo = []
    for doc in documents:
        known = indexed.get(doc.id)
        if known and known["digest"] == doc.digest and _processed(statuses.get(doc.id)):
            indexed[doc.id] = doc.metadata()  # its link or info can change without its text
            report.unchanged.append(doc.id)
        else:
            todo.append(doc)
    if limit is not None:
        todo, later = todo[: max(limit, 0)], todo[max(limit, 0) :]
        report.waiting = [doc.id for doc in later]
    if report.removed or report.unchanged:
        manifest.save()

    for number, doc in enumerate(todo):
        if number and pause:
            await asyncio.sleep(pause)  # the free model tier is rate limited
        outcome = await _insert(rag, doc, indexed, report, known=doc.id in statuses)
        manifest.save()  # after LightRAG wrote this document's storage: running searches reload on it
        if progress:
            progress(doc.id, outcome)
    return report


async def _insert(rag: Rag, doc: Document, indexed: dict[str, dict[str, Any]], report: ProcessReport, *, known: bool) -> str:
    """Process one document; LightRAG writes its storage files when the insert finishes."""
    if known:  # changed, or failed last time: LightRAG skips ids it already has
        await _delete(rag, doc.id)
    try:
        # The id doubles as LightRAG's file_path, which every retrieved entity and chunk carries.
        await rag.ainsert([doc.text], ids=[doc.id], file_paths=[doc.id])
    except Exception as exc:  # model, network and storage errors from LightRAG's layers
        raise SearchError(f"processing {doc.id} failed: {exc}") from exc
    status = (await rag.aget_docs_by_ids([doc.id])).get(doc.id)
    if _processed(status):
        outcome = "updated" if doc.id in indexed else "added"
        (report.updated if outcome == "updated" else report.added).append(doc.id)
        indexed[doc.id] = doc.metadata()
        return outcome
    report.failed[doc.id] = _field(status, "error_msg") or f"status {_field(status, 'status') or 'missing'}"
    indexed.pop(doc.id, None)
    return "failed"


async def _delete(rag: Rag, doc_id: str) -> None:
    result = await rag.adelete_by_doc_id(doc_id)
    status = _field(result, "status") or "success"
    if status not in ("success", "not_found"):
        raise SearchError(f"could not remove {doc_id} from the storage: {_field(result, 'message') or status}")


def _field(obj: Any, name: str) -> Any:
    return obj.get(name) if isinstance(obj, dict) else getattr(obj, name, None)


def _processed(status: Any) -> bool:
    return status is not None and _field(status, "status") == "processed"  # DocStatus is a str enum


def main(argv: Sequence[str] | None = None) -> int:
    parser = argparse.ArgumentParser(prog="process-storage", description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("--config", type=Path, help="Settings file (default: Search/config.toml)")
    parser.add_argument("--keep-removed", action="store_true", help="Keep entities that are no longer in the sources")
    parser.add_argument("--limit", type=int, help="Process at most this many new or changed documents, best first (the rest wait for the next run)")
    parser.add_argument("--pause", type=float, default=0.0, help="Seconds between documents, for rate-limited models (default 0)")
    parser.add_argument("--verbose", action="store_true", help="Show LightRAG's progress log")
    args = parser.parse_args(argv)
    logging.basicConfig(level=logging.WARNING, format="%(levelname)s %(name)s: %(message)s")
    logging.getLogger("lightrag").setLevel(logging.INFO if args.verbose else logging.WARNING)

    started = time.monotonic()

    def progress(doc_id: str, outcome: str) -> None:
        print(f"{time.monotonic() - started:6.0f}s  {outcome:<8} {doc_id}", flush=True)

    try:
        storage = ProcessStorage(SearchSettings.load(args.config))
        report = asyncio.run(storage.run(prune=not args.keep_removed, limit=args.limit, pause=args.pause, progress=progress))
    except SearchError as exc:
        print(f"error: {exc}", file=sys.stderr)
        return 2
    print(f"{report.summary()} in {time.monotonic() - started:.0f}s")
    for doc_id, error in report.failed.items():
        print(f"failed {doc_id}: {error}", file=sys.stderr)
    return 1 if report.failed else 0


if __name__ == "__main__":
    raise SystemExit(main())
