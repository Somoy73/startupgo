"""Structured AI provider contracts and an OpenAI-compatible implementation."""

from __future__ import annotations

import json
from abc import ABC, abstractmethod
from typing import Any, TypeVar, cast
from urllib.error import HTTPError, URLError
from urllib.request import Request, urlopen

from ..errors import ScraperError

T = TypeVar("T")


class AIProvider(ABC):
    @abstractmethod
    def generate_structured(
        self,
        *,
        system_prompt: str,
        user_prompt: str,
        response_type: type[T],
    ) -> T:
        """Generate and validate a structured response."""


class OpenAICompatibleProvider(AIProvider):
    """Call OpenAI-compatible chat APIs using only the Python standard library."""

    def __init__(self, *, endpoint: str, api_key: str, model: str, timeout: float = 60):
        self.endpoint = endpoint.rstrip("/")
        self.api_key = api_key
        self.model = model
        self.timeout = timeout

    def generate_structured(
        self,
        *,
        system_prompt: str,
        user_prompt: str,
        response_type: type[T],
    ) -> T:
        payload = {
            "model": self.model,
            "temperature": 0,
            "messages": [
                {"role": "system", "content": system_prompt},
                {"role": "user", "content": user_prompt},
            ],
            "response_format": {"type": "json_object"},
        }
        request = Request(
            f"{self.endpoint}/chat/completions",
            data=json.dumps(payload).encode("utf-8"),
            headers={
                "Authorization": f"Bearer {self.api_key}",
                "Content-Type": "application/json",
            },
            method="POST",
        )
        try:
            with urlopen(request, timeout=self.timeout) as response:
                result = json.loads(response.read().decode("utf-8"))
        except (HTTPError, URLError, TimeoutError, json.JSONDecodeError) as exc:
            raise ScraperError(f"AI provider request failed: {exc}") from exc

        try:
            content = result["choices"][0]["message"]["content"]
            data = json.loads(content)
            return _validate_response(data, response_type)
        except (KeyError, IndexError, TypeError, json.JSONDecodeError, ValueError) as exc:
            raise ScraperError("AI provider returned an invalid structured response") from exc


def _validate_response(data: Any, response_type: type[T]) -> T:
    validator = cast(Any, response_type)
    if hasattr(validator, "model_validate"):
        return cast(T, validator.model_validate(data))
    if hasattr(validator, "from_dict"):
        return cast(T, validator.from_dict(data))
    if hasattr(response_type, "__annotations__") and isinstance(data, dict):
        return response_type(**data)
    raise TypeError(f"{response_type!r} does not support structured validation")
