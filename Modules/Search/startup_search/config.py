"""Settings: which models and keys from .env (or the environment), everything else from config.toml.

    CHAT_MODEL, CHAT_API_KEY                            chat model: entities/relations, query keywords
    EMBEDDING_MODEL, EMBEDDING_API_KEY, EMBEDDING_DIM   embedding model and its vector size

Unset model names and the dimension fall back to the defaults below. Environment variables win
over .env.

STARTUPGO_SEARCH_CONFIG picks the config.toml when none is passed, e.g. the one refresh.py generates
for the runtime database (DB/runtime/config/search/config.toml); its .env is read from its folder.
"""

from __future__ import annotations

import os
import tomllib
from collections.abc import Mapping
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, ClassVar

from .errors import SearchError, SearchUnavailable

# config.toml next to the package, so commands work from any directory.
DEFAULT_CONFIG = Path(__file__).resolve().parents[1] / "config.toml"
NVIDIA_ENDPOINT = "https://integrate.api.nvidia.com/v1"
DEFAULT_CHAT_MODEL = "nvidia/nemotron-3.5-lightning-30b-a3b"
DEFAULT_EMBEDDING_MODEL = "nvidia/llama-3.2-nv-embedqa-1b-v1"
DEFAULT_EMBEDDING_DIM = 2048
QUERY_MODES = ("mix", "local", "global", "hybrid", "naive")


@dataclass(frozen=True, slots=True)
class ChatSettings:
    KEY_ENV: ClassVar[str] = "CHAT_API_KEY"

    model: str
    endpoint: str
    reasoning: bool  # Nemotron's thinking step; off is ~1 s per call instead of ~27 s
    max_tokens: int
    timeout: int  # seconds per call
    max_async: int  # parallel calls
    api_key: str = field(default="", repr=False)

    def require_key(self) -> str:
        return _require(self.api_key, self.KEY_ENV, self.model)


@dataclass(frozen=True, slots=True)
class EmbeddingSettings:
    KEY_ENV: ClassVar[str] = "EMBEDDING_API_KEY"

    model: str
    endpoint: str
    dim: int  # must match what the model returns
    max_token_size: int
    max_async: int
    api_key: str = field(default="", repr=False)

    def require_key(self) -> str:
        return _require(self.api_key, self.KEY_ENV, self.model)


@dataclass(frozen=True, slots=True)
class StorageSettings:
    working_dir: Path
    workspace: str
    kv: str
    vector: str
    graph: str
    doc_status: str


@dataclass(frozen=True, slots=True)
class QuerySettings:
    mode: str
    top_k: int
    chunk_top_k: int
    min_similarity: float  # vector matches below this cosine similarity are ignored
    max_results: int


@dataclass(frozen=True, slots=True)
class SearchSettings:
    chat: ChatSettings
    embedding: EmbeddingSettings
    storage: StorageSettings
    query: QuerySettings
    database: Path
    entries: Path

    @classmethod
    def load(cls, path: Path | None = None, *, env: Mapping[str, str] | None = None) -> SearchSettings:
        """Read ``path`` (default: $STARTUPGO_SEARCH_CONFIG, else config.toml next to the package) and
        ``env`` (default: .env next to it, overridden by the environment)."""
        path = path or Path(os.environ.get("STARTUPGO_SEARCH_CONFIG") or DEFAULT_CONFIG)
        root = path.resolve().parent
        if env is None:
            env = {**read_dotenv(root / ".env"), **os.environ}
        try:
            data = tomllib.loads(path.read_text(encoding="utf-8"))
        except (OSError, tomllib.TOMLDecodeError) as exc:
            raise SearchError(f"could not read configuration {path}: {exc}") from exc

        chat: dict[str, Any] = data.get("chat", {})
        embedding: dict[str, Any] = data.get("embedding", {})
        storage: dict[str, Any] = data.get("storage", {})
        query: dict[str, Any] = data.get("query", {})
        sources: dict[str, Any] = data.get("sources", {})
        mode = str(query.get("mode", "mix"))
        if mode not in QUERY_MODES:
            raise SearchError(f"[query] mode must be one of {', '.join(QUERY_MODES)}, got {mode!r}")
        dim = _value(env, "EMBEDDING_DIM") or str(DEFAULT_EMBEDDING_DIM)
        if not dim.isdigit():
            raise SearchError(f"EMBEDDING_DIM must be a whole number, got {dim!r}")

        return cls(
            chat=ChatSettings(
                model=_value(env, "CHAT_MODEL") or DEFAULT_CHAT_MODEL,
                endpoint=str(chat.get("endpoint", NVIDIA_ENDPOINT)),
                reasoning=bool(chat.get("reasoning", False)),
                max_tokens=int(chat.get("max_tokens", 4096)),
                timeout=int(chat.get("timeout", 120)),
                max_async=int(chat.get("max_async", 2)),
                api_key=_value(env, ChatSettings.KEY_ENV),
            ),
            embedding=EmbeddingSettings(
                model=_value(env, "EMBEDDING_MODEL") or DEFAULT_EMBEDDING_MODEL,
                endpoint=str(embedding.get("endpoint", NVIDIA_ENDPOINT)),
                dim=int(dim),
                max_token_size=int(embedding.get("max_token_size", 8192)),
                max_async=int(embedding.get("max_async", 2)),
                api_key=_value(env, EmbeddingSettings.KEY_ENV),
            ),
            storage=StorageSettings(
                working_dir=root / storage.get("working_dir", "rag_storage"),
                workspace=str(storage.get("workspace", "")),
                kv=str(storage.get("kv", "JsonKVStorage")),
                vector=str(storage.get("vector", "NanoVectorDBStorage")),
                graph=str(storage.get("graph", "NetworkXStorage")),
                doc_status=str(storage.get("doc_status", "JsonDocStatusStorage")),
            ),
            query=QuerySettings(
                mode=mode,
                top_k=int(query.get("top_k", 40)),
                chunk_top_k=int(query.get("chunk_top_k", 20)),
                min_similarity=float(query.get("min_similarity", 0.2)),
                max_results=int(query.get("max_results", 20)),
            ),
            # The Backend's STARTUPGO_DB override applies here too, so both read the same database.
            database=Path(_value(env, "STARTUPGO_DB") or root / sources.get("database", "../../DB/startupgo.db")),
            entries=root / sources.get("entries", "../Agent/output/startups"),
        )


def _value(env: Mapping[str, str], name: str) -> str:
    return (env.get(name) or "").strip()


def _require(key: str, env_name: str, model: str) -> str:
    if not key:
        raise SearchUnavailable(f"missing API key for {model}: set {env_name} in Search/.env")
    return key


def read_dotenv(path: Path) -> dict[str, str]:
    """Simple KEY=VALUE lines; comments and blank lines are skipped. Nothing is put in os.environ."""
    if not path.exists():
        return {}
    values = {}
    for line in path.read_text(encoding="utf-8").splitlines():
        stripped = line.strip()
        if not stripped or stripped.startswith("#") or "=" not in stripped:
            continue
        key, value = stripped.split("=", 1)
        values[key.strip()] = value.strip().strip("\"'")
    return values
