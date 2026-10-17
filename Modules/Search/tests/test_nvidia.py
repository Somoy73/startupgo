"""NVIDIA model functions handed to LightRAG, and the model settings."""

import asyncio
import os
from pathlib import Path

import numpy as np
import pytest
from lightrag.utils import Tokenizer

from startup_search import nvidia
from startup_search.config import DEFAULT_CONFIG, SearchSettings
from startup_search.errors import SearchError, SearchUnavailable
from startup_search.storage import build_rag

from .helpers import CharTokenizer, settings


def test_chat_calls_the_nvidia_endpoint_with_thinking_off(monkeypatch, tmp_path):
    calls = []

    async def fake_complete(model, prompt, **kwargs):
        calls.append({"model": model, "prompt": prompt, **kwargs})
        return "ok"

    monkeypatch.setattr(nvidia, "_complete", fake_complete)
    s = settings(tmp_path)
    complete = nvidia.chat_model(s.chat, "key")
    answer = asyncio.run(complete("extract", system_prompt="sys", hashing_kv="cache", response_format={"type": "json_object"}))
    assert answer == "ok"
    call = calls[0]
    assert call["model"] == "nvidia/nemotron-3.5-lightning-30b-a3b"
    assert (call["base_url"], call["api_key"]) == ("https://integrate.api.nvidia.com/v1", "key")
    assert call["extra_body"] == {"chat_template_kwargs": {"enable_thinking": False}}
    assert (call["max_tokens"], call["timeout"], call["system_prompt"]) == (4096, 120, "sys")
    assert call["hashing_kv"] == "cache" and call["response_format"] == {"type": "json_object"}  # LightRAG's own arguments pass through


def test_embeddings_tell_queries_from_passages(monkeypatch, tmp_path):
    calls = []

    async def fake_embed(texts, **kwargs):
        calls.append(kwargs)
        return np.ones((len(texts), 64))

    monkeypatch.setattr(nvidia, "_embed", fake_embed)
    s = settings(tmp_path)
    embed = nvidia.embedding_model(s.embedding, "key")
    assert embed.embedding_dim == 64 and embed.supports_asymmetric and embed.model_name == "nvidia/llama-3.2-nv-embedqa-1b-v1"

    asyncio.run(embed(["what about kelp"], context="query"))
    asyncio.run(embed(["# Notpla", "seaweed"], context="document"))
    assert [c["input_type"] for c in calls] == ["query", "passage"]
    assert calls[0]["trunc"] == "END" and calls[0]["model"] == "nvidia/llama-3.2-nv-embedqa-1b-v1"


def test_wrong_embedding_size_is_caught(monkeypatch, tmp_path):
    async def fake_embed(texts, **kwargs):
        return np.ones((len(texts), 10))

    monkeypatch.setattr(nvidia, "_embed", fake_embed)
    s = settings(tmp_path)
    embed = nvidia.embedding_model(s.embedding, "key")
    with pytest.raises(ValueError, match="dimension"):
        asyncio.run(embed(["a"]))


def test_defaults_when_env_sets_no_models():
    s = SearchSettings.load(DEFAULT_CONFIG, env={})
    assert s.chat.model == "nvidia/nemotron-3.5-lightning-30b-a3b" and s.chat.reasoning is False
    assert (s.embedding.model, s.embedding.dim) == ("nvidia/llama-3.2-nv-embedqa-1b-v1", 2048)
    assert s.chat.api_key == s.embedding.api_key == ""
    assert s.query.mode == "mix" and s.database.name == "startupgo_unified.db" and s.entries.parts[-2:] == ("output", "startups")


def test_models_and_their_keys_come_from_env(tmp_path):
    env = {"CHAT_MODEL": "chat-m", "CHAT_API_KEY": "chat-key", "EMBEDDING_MODEL": "embed-m", "EMBEDDING_API_KEY": "embed-key"}
    s = settings(tmp_path, env=env)
    assert (s.chat.model, s.chat.require_key()) == ("chat-m", "chat-key")
    assert (s.embedding.model, s.embedding.require_key(), s.embedding.dim) == ("embed-m", "embed-key", 64)
    assert "chat-key" not in repr(s) and "embed-key" not in repr(s)
    rag = build_rag(s, tokenizer=Tokenizer("chars", CharTokenizer()))
    assert rag.llm_model_name == "chat-m" and rag.embedding_func.model_name == "embed-m"


@pytest.mark.parametrize(("env", "missing"), [({}, "CHAT_API_KEY"), ({"CHAT_API_KEY": "c"}, "EMBEDDING_API_KEY")])
def test_each_model_needs_its_key(tmp_path, env, missing):
    with pytest.raises(SearchUnavailable, match=missing):
        build_rag(settings(tmp_path, env=env), tokenizer=Tokenizer("chars", CharTokenizer()))


def test_dotenv_file_is_read_and_the_environment_wins(tmp_path, monkeypatch):
    (tmp_path / "config.toml").write_text("")
    (tmp_path / ".env").write_text("# models\nCHAT_MODEL=from-file\nEMBEDDING_MODEL='quoted-model'\nEMBEDDING_DIM=1024\n")
    for name in ("CHAT_MODEL", "EMBEDDING_MODEL", "EMBEDDING_DIM"):
        monkeypatch.delenv(name, raising=False)
    monkeypatch.setenv("CHAT_MODEL", "from-environment")
    s = SearchSettings.load(tmp_path / "config.toml")
    assert (s.chat.model, s.embedding.model, s.embedding.dim) == ("from-environment", "quoted-model", 1024)
    assert "EMBEDDING_MODEL" not in os.environ  # .env values aren't copied into the process environment


def test_database_follows_the_backends_override(tmp_path):
    assert settings(tmp_path, env={"STARTUPGO_DB": "/data/other.db"}).database == Path("/data/other.db")
    assert settings(tmp_path).database == tmp_path / "../../DB/startupgo_unified.db"


def test_config_file_follows_the_runtime_override(tmp_path, monkeypatch):
    runtime = tmp_path / "runtime" / "config.toml"
    runtime.parent.mkdir()
    runtime.write_text('[storage]\nworking_dir = "rag_storage"\n', encoding="utf-8")
    monkeypatch.setenv("STARTUPGO_SEARCH_CONFIG", str(runtime))
    assert SearchSettings.load(env={}).storage.working_dir == runtime.parent / "rag_storage"
    assert SearchSettings.load(DEFAULT_CONFIG, env={}).storage.working_dir == DEFAULT_CONFIG.parent / "rag_storage"  # an explicit path wins
    monkeypatch.delenv("STARTUPGO_SEARCH_CONFIG")
    assert SearchSettings.load(env={}).storage.working_dir == DEFAULT_CONFIG.parent / "rag_storage"


def test_bad_settings(tmp_path):
    with pytest.raises(SearchError, match="mode"):
        settings(tmp_path, '[query]\nmode = "fast"\n')
    with pytest.raises(SearchError, match="EMBEDDING_DIM"):
        settings(tmp_path, env={"EMBEDDING_DIM": "large"})
