"""LightRAG's four storages, local JSON files in [storage] working_dir for now, and the document manifest.

    kv          JsonKVStorage         documents, chunks, entity/relation records, model-answer cache
    vector      NanoVectorDBStorage   embeddings of chunks, entities and relations (vdb_*.json)
    graph       NetworkXStorage       the knowledge graph (graph_chunk_entity_relation.graphml)
    doc_status  JsonDocStatusStorage  processing state of each document

The manifest (startupgo_documents.json, same folder) records what ProcessStorage indexed: each
document's text digest, so unchanged documents aren't processed again, and the startup info a search
match returns.
"""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any, Protocol

from .config import SearchSettings
from .errors import SearchError

MANIFEST = "startupgo_documents.json"


class Rag(Protocol):
    """The part of LightRAG this package uses."""

    chunk_entity_relation_graph: Any  # BaseGraphStorage: read by the graph walk (graph.py)

    async def initialize_storages(self) -> None: ...
    async def finalize_storages(self) -> None: ...
    async def ainsert(self, input: list[str], *, ids: list[str], file_paths: list[str]) -> Any: ...
    async def aget_docs_by_ids(self, ids: list[str]) -> dict[str, Any]: ...
    async def adelete_by_doc_id(self, doc_id: str) -> Any: ...
    async def aquery_data(self, query: str, param: Any) -> dict[str, Any]: ...


def build_rag(
    settings: SearchSettings,
    *,
    read_only: bool = False,
    llm: Any = None,
    embedding: Any = None,
    tokenizer: Any = None,
) -> Rag:
    """LightRAG on the configured storages with the chat and embedding models (tests pass fakes).

    ``read_only`` is for searching: query answers aren't cached, so a search never writes the
    storage files that ProcessStorage writes (possibly in another process at the same time).
    """
    from lightrag import LightRAG

    from .nvidia import chat_model, embedding_model

    chat = settings.chat
    llm = llm or chat_model(chat, chat.require_key())
    embedding = embedding or embedding_model(settings.embedding, settings.embedding.require_key())
    storage = settings.storage
    storage.working_dir.mkdir(parents=True, exist_ok=True)
    options: dict[str, Any] = {"tokenizer": tokenizer} if tokenizer is not None else {}
    return LightRAG(
        working_dir=str(storage.working_dir),
        workspace=storage.workspace,
        kv_storage=storage.kv,
        vector_storage=storage.vector,
        graph_storage=storage.graph,
        doc_status_storage=storage.doc_status,
        llm_model_func=llm,
        llm_model_name=chat.model,
        llm_model_max_async=chat.max_async,
        default_llm_timeout=chat.timeout,
        embedding_func=embedding,
        embedding_func_max_async=settings.embedding.max_async,
        cosine_better_than_threshold=settings.query.min_similarity,
        enable_llm_cache=not read_only,
        **options,
    )


class Manifest:
    """Indexed document id -> Document.metadata(), kept in a JSON file next to LightRAG's storage."""

    def __init__(self, settings: SearchSettings):
        workspace = settings.storage.workspace
        self.path: Path = settings.storage.working_dir / (f"{workspace}_{MANIFEST}" if workspace else MANIFEST)
        self.documents: dict[str, dict[str, Any]] = {}

    def load(self) -> Manifest:
        try:
            data = json.loads(self.path.read_text(encoding="utf-8"))
        except FileNotFoundError:
            data = {}
        except (OSError, json.JSONDecodeError) as exc:
            raise SearchError(f"could not read {self.path}: {exc}") from exc
        self.documents = dict(data.get("documents", {}))
        return self

    def save(self) -> None:
        self.path.parent.mkdir(parents=True, exist_ok=True)
        temporary = self.path.with_suffix(".tmp")
        content = {"version": 1, "documents": dict(sorted(self.documents.items()))}
        temporary.write_text(json.dumps(content, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
        temporary.replace(self.path)

    def modified(self) -> float | None:
        """When ProcessStorage last wrote it (None if never), so a running search can reload."""
        try:
            return self.path.stat().st_mtime
        except FileNotFoundError:
            return None
