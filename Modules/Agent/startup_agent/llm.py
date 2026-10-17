"""LLM clients that return JSON constrained by a JSON Schema."""

from __future__ import annotations

import hashlib
import json
import time
from collections.abc import Callable
from dataclasses import dataclass
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
MAX_RETRY_DELAY = 60.0
THINKING_LEVELS = ("minimal", "low", "medium", "high")


class QuotaExhausted(AgentError):
    """A quota is used up (429 without a retry delay); further calls of that kind are skipped this run."""


@dataclass(slots=True)
class UsageStats:
    """What the run cost: requests, cache hits, waiting, tokens."""

    llm_requests: int = 0
    llm_cached: int = 0
    search_requests: int = 0
    search_cached: int = 0
    retries: int = 0
    skipped: int = 0  # calls not sent because that quota was exhausted earlier in the run
    waited_seconds: float = 0.0  # rate-limit pacing and retry backoff
    prompt_tokens: int = 0
    output_tokens: int = 0
    thinking_tokens: int = 0

    def summary(self) -> str:
        parts = [
            f"LLM {self.llm_requests} request(s), {self.llm_cached} cached",
            f"search {self.search_requests} request(s), {self.search_cached} cached",
            f"{self.retries} retr{'y' if self.retries == 1 else 'ies'}",
            f"{self.waited_seconds:.0f}s waiting for rate limits",
            f"tokens in {self.prompt_tokens:,} / out {self.output_tokens:,} / thinking {self.thinking_tokens:,}",
        ]
        if self.skipped:
            parts.append(f"{self.skipped} call(s) skipped (quota exhausted)")
        return "; ".join(parts)


class RateLimiter:
    """Spaces requests evenly so a burst never exceeds the per-minute limit."""

    def __init__(self, requests_per_minute: float, *, clock: Callable[[], float] = time.monotonic, sleep: Callable[[float], None] = time.sleep):
        self.interval = 60.0 / requests_per_minute
        self._clock = clock
        self._sleep = sleep
        self._next = 0.0

    def wait(self) -> float:
        """Block until the next request may be sent; returns the seconds waited."""
        now = self._clock()
        delay = max(0.0, self._next - now)
        if delay:
            self._sleep(delay)
        self._next = max(now, self._next) + self.interval
        return delay


def _retry_delay(exc: Any, attempt: int) -> float | None:
    """Seconds to wait before retrying, or None to fail now.

    Server errors back off. A 429 is retried only when the API says how long to wait
    (per-minute rate limits); without RetryInfo it is an exhausted quota and retrying is futile.
    """
    if attempt >= len(BACKOFF_SECONDS) or exc.code not in RETRYABLE_STATUS:
        return None
    if exc.code != 429:
        return BACKOFF_SECONDS[attempt]
    details = (exc.details or {}).get("error", {}).get("details", []) if isinstance(exc.details, dict) else []
    for detail in details:
        if str(detail.get("@type", "")).endswith("RetryInfo"):
            delay = str(detail.get("retryDelay", "")).rstrip("s")
            try:
                return min(float(delay), MAX_RETRY_DELAY)
            except ValueError:
                return BACKOFF_SECONDS[attempt]
    return None


class GeminiSession:
    """One Gemini client shared by extraction, the judge and web search.

    They all draw on the same per-minute quota, so they share one rate limiter. Exhausted quotas
    are remembered per kind ("llm" vs "search": grounding has its own quota) and not called again.
    """

    def __init__(
        self,
        client_factory: Callable[[], Any],
        *,
        stats: UsageStats | None = None,
        limiter: RateLimiter | None = None,
        thinking: str = "",
        sleep: Callable[[float], None] = time.sleep,
    ):
        if thinking and thinking not in THINKING_LEVELS:
            raise AgentError(f"[llm] thinking must be one of {', '.join(THINKING_LEVELS)} or empty, not {thinking!r}")
        self._client_factory = client_factory
        self._client: Any = None
        self.stats = stats or UsageStats()
        self._limiter = limiter
        self.thinking = thinking
        self._sleep = sleep
        self._exhausted: dict[str, str] = {}

    def available(self, kind: str) -> bool:
        return kind not in self._exhausted

    def generate(self, *, model: str, contents: str, kind: str, **config: Any) -> Any:
        from google.genai import errors, types

        if kind in self._exhausted:
            self.stats.skipped += 1
            raise QuotaExhausted(f"skipped: Gemini {kind} quota exhausted earlier in this run ({self._exhausted[kind]})")
        self._client = self._client or self._client_factory()
        attempt = 0
        while True:
            thinking = {"thinking_config": types.ThinkingConfig(thinking_level=self.thinking.upper())} if self.thinking else {}
            if self._limiter:
                self.stats.waited_seconds += self._limiter.wait()
            if kind == "search":
                self.stats.search_requests += 1
            else:
                self.stats.llm_requests += 1
            try:
                response = self._client.models.generate_content(
                    model=model, contents=contents, config=types.GenerateContentConfig(**config, **thinking)
                )
            except errors.APIError as exc:
                if exc.code == 400 and self.thinking and "think" in str(exc).lower():
                    self.thinking = ""  # this model doesn't accept the thinking setting: use its default
                    continue
                delay = _retry_delay(exc, attempt)
                if delay is None:
                    if exc.code == 429:
                        self._exhausted[kind] = str(exc)[:120]
                        raise QuotaExhausted(f"Gemini {kind} quota exhausted: {exc}") from exc
                    raise AgentError(f"Gemini request failed after {attempt + 1} attempt(s): {exc}") from exc
                self.stats.retries += 1
                self.stats.waited_seconds += delay
                self._sleep(delay)
                attempt += 1
                continue
            self._record_usage(response)
            return response

    def _record_usage(self, response: Any) -> None:
        usage = getattr(response, "usage_metadata", None)
        if usage:
            self.stats.prompt_tokens += usage.prompt_token_count or 0
            self.stats.output_tokens += usage.candidates_token_count or 0
            self.stats.thinking_tokens += usage.thoughts_token_count or 0


def gemini_client(api_key: str) -> Any:
    try:
        from google import genai
    except ImportError as exc:  # pragma: no cover - dependency is declared
        raise AgentError("Gemini support requires the google-genai package") from exc
    return genai.Client(api_key=api_key)


class GeminiClient:
    def __init__(self, session: GeminiSession, *, model: str, temperature: float = 0.0):
        self.session = session
        self.model = model
        self.temperature = temperature

    def complete_json(self, *, system: str, user: str, schema: dict[str, Any]) -> dict[str, Any]:
        response = self.session.generate(
            model=self.model,
            contents=user,
            kind="llm",
            system_instruction=system,
            temperature=self.temperature,
            response_mime_type="application/json",
            response_json_schema=schema,
        )
        return _parse(response.text)


class OpenAICompatibleClient:
    """Any /chat/completions endpoint that supports response_format json_schema."""

    def __init__(
        self,
        *,
        endpoint: str,
        api_key: str,
        model: str,
        temperature: float = 0.0,
        timeout: float = 120,
        max_tokens: int | None = None,
        extra_body: dict[str, Any] | None = None,  # provider-specific fields, e.g. NVIDIA's chat_template_kwargs
    ):
        if not endpoint:
            raise AgentError("[llm] endpoint is required for the openai-compatible provider")
        self.endpoint = endpoint.rstrip("/")
        self.api_key = api_key
        self.model = model
        self.temperature = temperature
        self.timeout = timeout
        self.max_tokens = max_tokens
        self.extra_body = extra_body or {}

    def complete_json(self, *, system: str, user: str, schema: dict[str, Any]) -> dict[str, Any]:
        payload = {
            "model": self.model,
            "temperature": self.temperature,
            "messages": [{"role": "system", "content": system}, {"role": "user", "content": user}],
            "response_format": {"type": "json_schema", "json_schema": {"name": "result", "schema": schema, "strict": True}},
            **({"max_tokens": self.max_tokens} if self.max_tokens else {}),
            **self.extra_body,
        }
        request = Request(
            f"{self.endpoint}/chat/completions",
            data=json.dumps(payload).encode("utf-8"),
            headers={"Authorization": f"Bearer {self.api_key}", "Content-Type": "application/json", "Accept": "application/json"},
            method="POST",
        )
        try:
            with urlopen(request, timeout=self.timeout) as response:
                body = json.loads(response.read().decode("utf-8"))
        except HTTPError as exc:
            detail = exc.read().decode("utf-8", errors="replace")[:300]
            raise AgentError(f"LLM request failed ({exc.code}): {detail}") from exc
        except (URLError, TimeoutError, json.JSONDecodeError) as exc:
            raise AgentError(f"LLM request failed: {exc}") from exc
        try:
            choice = body["choices"][0]
            content = choice["message"].get("content")
        except (KeyError, IndexError, TypeError) as exc:
            raise AgentError("LLM response has no choices") from exc
        if not content:
            # Reasoning models can spend the whole token budget thinking and return no answer.
            raise AgentError(f"LLM returned no content (finish_reason {choice.get('finish_reason')!r})")
        return _parse(content)


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

    def __init__(self, inner: LLMClient, cache: JsonCache, *, stats: UsageStats | None = None):
        self.inner = inner
        self.model = inner.model
        self.cache = cache
        self.stats = stats

    def complete_json(self, *, system: str, user: str, schema: dict[str, Any]) -> dict[str, Any]:
        key = hashlib.sha256(json.dumps([self.model, system, user, schema], sort_keys=True).encode()).hexdigest()
        if (cached := self.cache.get("llm", key)) is not None:
            if self.stats:
                self.stats.llm_cached += 1
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
