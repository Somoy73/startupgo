"""LightRAG model functions for NVIDIA's hosted API (OpenAI-compatible; free keys at build.nvidia.com).

Chat: LightRAG calls it to extract entities and relations from each chunk (process-storage) and
keywords from each query (search). Nemotron models "think" before answering by default (about 27 s
per call in our test, often without an answer within the token budget), so that is switched off
unless [chat] reasoning = true.

Embeddings: NVIDIA's retrieval models embed questions and passages differently (input_type "query"
or "passage"). LightRAG says which one it needs through its ``context`` argument.
"""

from __future__ import annotations

from collections.abc import Awaitable, Callable
from typing import Any

import numpy as np
from lightrag.llm.nvidia_openai import nvidia_openai_embed
from lightrag.llm.openai import openai_complete_if_cache
from lightrag.utils import EmbeddingFunc

from .config import ChatSettings, EmbeddingSettings

# The undecorated NVIDIA embedding call (still retried on rate limits); module-level so tests can swap it.
_embed = nvidia_openai_embed.func
_complete = openai_complete_if_cache

ChatFunc = Callable[..., Awaitable[str]]


def chat_model(settings: ChatSettings, api_key: str) -> ChatFunc:
    """LightRAG's ``llm_model_func`` for an NVIDIA chat model."""

    async def complete(
        prompt: str,
        system_prompt: str | None = None,
        history_messages: list[dict[str, Any]] | None = None,
        **kwargs: Any,
    ) -> str:
        extra_body = kwargs.pop("extra_body", None) or {}
        kwargs.setdefault("max_tokens", settings.max_tokens)
        kwargs.setdefault("timeout", settings.timeout)
        return await _complete(
            settings.model,
            prompt,
            system_prompt=system_prompt,
            history_messages=history_messages or [],
            base_url=settings.endpoint,
            api_key=api_key,
            extra_body={**extra_body, "chat_template_kwargs": {"enable_thinking": settings.reasoning}},
            **kwargs,
        )

    return complete


def embedding_model(settings: EmbeddingSettings, api_key: str) -> EmbeddingFunc:
    """LightRAG's ``embedding_func`` for an NVIDIA retrieval embedding model."""

    async def embed(texts: list[str], context: str = "document") -> np.ndarray:
        return await _embed(
            texts,
            model=settings.model,
            base_url=settings.endpoint,
            api_key=api_key,
            input_type="query" if context == "query" else "passage",
            trunc="END",  # cut overlong text instead of failing the request
        )

    return EmbeddingFunc(
        embedding_dim=settings.dim,
        func=embed,
        max_token_size=settings.max_token_size,
        model_name=settings.model,
        supports_asymmetric=True,
    )
