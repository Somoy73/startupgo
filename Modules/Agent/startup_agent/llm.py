"""LLM clients that return JSON constrained by a JSON Schema."""

from __future__ import annotations

import hashlib
import json
import time
from collections.abc import Callable
from typing import Any, Protocol
from urllib.error import HTTPError, URLError
from urllib.request import Request, urlopen

from .cache import JsonCache
from .errors import AgentError


class LLMClient(Protocol):
    model: str

    def complete_json(self, *, system: str, user: str, schema: dict[str, Any]) -> dict[str, Any]: ...


RETRYABLE_STATUS = {429, 500, 503}
BACKOFF_SECONDS = (5, 20, 60)


class GeminiClient:
    def __init__(self, *, api_key: str, model: str, temperature: float = 0.0):
        try:
            from google import genai
        except ImportError as exc:  # pragma: no cover - dependency is declared
            raise AgentError("Gemini support requires the google-genai package") from exc
        self.model = model
        self.temperature = temperature
        self._client = genai.Client(api_key=api_key)

    def complete_json(self, *, system: str, user: str, schema: dict[str, Any]) -> dict[str, Any]:
        from google.genai import errors, types

        config = types.GenerateContentConfig(
            system_instruction=system,
            temperature=self.temperature,
            response_mime_type="application/json",
            response_json_schema=schema,
        )
        attempt = 0
        while True:
            try:
                response = self._client.models.generate_content(model=self.model, contents=user, config=config)
                return _parse(response.text)
            except errors.APIError as exc:
                if exc.code not in RETRYABLE_STATUS or attempt >= len(BACKOFF_SECONDS):
                    raise AgentError(f"Gemini request failed after {attempt + 1} attempt(s): {exc}") from exc
                time.sleep(BACKOFF_SECONDS[attempt])  # rate limit or transient server error
                attempt += 1


class OpenAICompatibleClient:
    """Any /chat/completions endpoint that supports response_format json_schema."""

    def __init__(self, *, endpoint: str, api_key: str, model: str, temperature: float = 0.0, timeout: float = 120):
        if not endpoint:
            raise AgentError("[llm] endpoint is required for the openai-compatible provider")
        self.endpoint = endpoint.rstrip("/")
        self.api_key = api_key
        self.model = model
        self.temperature = temperature
        self.timeout = timeout

    def complete_json(self, *, system: str, user: str, schema: dict[str, Any]) -> dict[str, Any]:
        payload = {
            "model": self.model,
            "temperature": self.temperature,
            "messages": [{"role": "system", "content": system}, {"role": "user", "content": user}],
            "response_format": {"type": "json_schema", "json_schema": {"name": "facts", "schema": schema, "strict": True}},
        }
        request = Request(
            f"{self.endpoint}/chat/completions",
            data=json.dumps(payload).encode("utf-8"),
            headers={"Authorization": f"Bearer {self.api_key}", "Content-Type": "application/json"},
            method="POST",
        )
        try:
            with urlopen(request, timeout=self.timeout) as response:
                body = json.loads(response.read().decode("utf-8"))
            return _parse(body["choices"][0]["message"]["content"])
        except (HTTPError, URLError, TimeoutError, KeyError, IndexError, json.JSONDecodeError) as exc:
            raise AgentError(f"LLM request failed: {exc}") from exc


class LazyLLM:
    """Creates the real client on first use, so commands and cached reruns that make no LLM call need no API key."""

    def __init__(self, factory: Callable[[], LLMClient], *, model: str):
        self._factory = factory
        self._client: LLMClient | None = None
        self.model = model

    def complete_json(self, *, system: str, user: str, schema: dict[str, Any]) -> dict[str, Any]:
        if self._client is None:
            self._client = self._factory()
        return self._client.complete_json(system=system, user=user, schema=schema)


class CachedLLM:
    """Caches responses by (model, prompts, schema) so reruns cost nothing."""

    def __init__(self, inner: LLMClient, cache: JsonCache):
        self.inner = inner
        self.model = inner.model
        self.cache = cache

    def complete_json(self, *, system: str, user: str, schema: dict[str, Any]) -> dict[str, Any]:
        key = hashlib.sha256(json.dumps([self.model, system, user, schema], sort_keys=True).encode()).hexdigest()
        if (cached := self.cache.get("llm", key)) is not None:
            return cached["response"]
        response = self.inner.complete_json(system=system, user=user, schema=schema)
        self.cache.put("llm", key, {"model": self.model, "response": response})
        return response


def _parse(text: str | None) -> dict[str, Any]:
    try:
        data = json.loads(text or "")
    except json.JSONDecodeError as exc:
        raise AgentError("LLM returned invalid JSON") from exc
    if not isinstance(data, dict):
        raise AgentError("LLM returned JSON that is not an object")
    return data
