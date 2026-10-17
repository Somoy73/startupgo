"""Fakes: LightRAG's storage-and-retrieval surface, and chat/embedding models for the real LightRAG."""

from __future__ import annotations

import hashlib
import json
import re
from pathlib import Path
from types import SimpleNamespace
from typing import Any

import numpy as np

from startup_search.config import SearchSettings
from startup_search.documents import Document

TOPICS = ("seaweed", "kelp", "plastic", "buoys", "packaging")
DELIMITER, COMPLETE = "<|#|>", "<|COMPLETE|>"


def settings(tmp_path: Path, extra: str = "", env: dict[str, str] | None = None) -> SearchSettings:
    """Settings for a storage in tmp_path; models and keys from ``env`` only (never the real .env)."""
    config = tmp_path / "config.toml"
    config.write_text(f'[storage]\nworking_dir = "rag"\n{extra}', encoding="utf-8")
    return SearchSettings.load(config, env={"EMBEDDING_DIM": "64", **(env or {})})


def doc(doc_id: str, text: str, *, name: str | None = None, startup: str | None = None, entry: str | None = None, **kw: Any) -> Document:
    key, kind = (f"startup:{startup}", "startup") if startup else (None, "entry")
    return Document(doc_id, text, name or doc_id.split(":", 1)[1].title(), kw.get("website"), startup, entry, kw.get("info", {}), key, kind)


class FakeRag:
    """Records inserts and deletions; answers queries with a canned aquery_data response."""

    def __init__(self, response: dict[str, Any] | None = None, fail: set[str] = frozenset()):
        self.statuses: dict[str, SimpleNamespace] = {}
        self.inserted: list[list[str]] = []
        self.file_paths: list[list[str]] = []
        self.deleted: list[str] = []
        self.queries: list[tuple[str, Any]] = []
        self.response = response or {"status": "success", "data": {}, "metadata": {}}
        self.fail = set(fail)

    async def initialize_storages(self) -> None: ...

    async def finalize_storages(self) -> None: ...

    async def ainsert(self, input: list[str], *, ids: list[str], file_paths: list[str]) -> str:
        self.inserted.append(ids)
        self.file_paths.append(file_paths)
        for doc_id in ids:
            failed = doc_id in self.fail
            self.statuses[doc_id] = SimpleNamespace(status="failed" if failed else "processed", error_msg="model timeout" if failed else None)
        return "track"

    async def aget_docs_by_ids(self, ids: list[str]) -> dict[str, Any]:
        return {i: self.statuses[i] for i in ids if i in self.statuses}

    async def adelete_by_doc_id(self, doc_id: str) -> Any:
        self.deleted.append(doc_id)
        self.statuses.pop(doc_id, None)
        return SimpleNamespace(status="success", message="")

    async def aquery_data(self, query: str, param: Any) -> dict[str, Any]:
        self.queries.append((query, param))
        if isinstance(self.response, Exception):
            raise self.response
        return self.response


# --- fake models for the real LightRAG ---------------------------------------------------------


async def fake_llm(prompt: str, system_prompt: str | None = None, history_messages: Any = None, **kwargs: Any) -> str:
    """Keyword extraction: the query's topic words. Entity extraction: each "# Name" plus its topics."""
    if "high_level_keywords" in (system_prompt or "") + prompt:
        query = prompt.rsplit("Query", 1)[-1].lower()
        return json.dumps({"high_level_keywords": ["startups"], "low_level_keywords": [t for t in TOPICS if t in query]})
    rows = []
    for name in re.findall(r"^# (.+)$", prompt, re.M):
        rows.append(f"entity{DELIMITER}{name}{DELIMITER}organization{DELIMITER}{name} is a startup.")
        section = prompt.split(f"# {name}", 1)[1].split("\n# ", 1)[0].lower()
        for topic in TOPICS:
            if topic in section:
                rows.append(f"entity{DELIMITER}{topic.title()}{DELIMITER}concept{DELIMITER}{topic.title()} as a business.")
                rows.append(f"relation{DELIMITER}{name}{DELIMITER}{topic.title()}{DELIMITER}works on{DELIMITER}{name} works on {topic}.")
    return "\n".join([*rows, COMPLETE])


async def fake_embed(texts: list[str], **kwargs: Any) -> np.ndarray:
    """Bag of words hashed into 64 dimensions, normalised: shared words mean similar vectors."""
    vectors = np.zeros((len(texts), 64))
    for row, text in enumerate(texts):
        for word in re.findall(r"[a-z]+", text.lower()):
            vectors[row, int(hashlib.md5(word.encode()).hexdigest(), 16) % 64] += 1
        vectors[row] /= max(np.linalg.norm(vectors[row]), 1e-9)
    return vectors


class CharTokenizer:
    """One token per character: no tiktoken download in tests."""

    def encode(self, content: str) -> list[int]:
        return [ord(c) for c in content]

    def decode(self, tokens: list[int]) -> str:
        return "".join(map(chr, tokens))
