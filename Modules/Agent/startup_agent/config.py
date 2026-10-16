"""Agent settings from config.toml, secrets from .env."""

from __future__ import annotations

import os
import tomllib
from dataclasses import dataclass
from pathlib import Path
from typing import Any

from scraper.browser import BrowserSettings

from .errors import AgentError
from .scoring import DEFAULT_WEIGHTS


@dataclass(frozen=True, slots=True)
class LLMSettings:
    provider: str
    model: str
    api_key_env: str
    endpoint: str
    temperature: float

    def api_key(self) -> str:
        key = os.getenv(self.api_key_env, "").strip()
        if not key:
            raise AgentError(f"missing LLM credential: set {self.api_key_env} in .env")
        return key


@dataclass(frozen=True, slots=True)
class CrawlSettings:
    max_pages: int  # pages per startup website, homepage included
    page_chars: int  # text kept per page
    section_chars: int  # document text sent with each section call
    timeout: float
    delay: float  # seconds between requests
    browser: bool  # render pages with Chrome (see [browser])
    respect_robots: bool


@dataclass(frozen=True, slots=True)
class AgentSettings:
    root: Path
    llm: LLMSettings
    crawl: CrawlSettings
    browser: BrowserSettings
    weights: dict[str, float]
    cache_dir: Path
    output_dir: Path
    system_prompt: Path
    section_prompt: Path

    @classmethod
    def load(cls, path: Path) -> AgentSettings:
        root = path.resolve().parent
        load_dotenv(root / ".env")
        try:
            data = tomllib.loads(path.read_text(encoding="utf-8"))
        except (OSError, tomllib.TOMLDecodeError) as exc:
            raise AgentError(f"could not read configuration {path}: {exc}") from exc

        llm: dict[str, Any] = data.get("llm", {})
        crawl: dict[str, Any] = data.get("crawl", {})
        paths: dict[str, Any] = data.get("paths", {})
        weights = {**DEFAULT_WEIGHTS, **{k: float(v) for k, v in data.get("weights", {}).items()}}
        if unknown := set(weights) - set(DEFAULT_WEIGHTS):
            raise AgentError(f"unknown [weights] criteria: {', '.join(sorted(unknown))}")

        return cls(
            root=root,
            llm=LLMSettings(
                provider=str(llm.get("provider", "gemini")).casefold(),
                model=str(llm.get("model", "gemini-3.8-flash")),
                api_key_env=str(llm.get("api_key_env", "GEMINI_API_KEY")),
                endpoint=str(llm.get("endpoint", "")),
                temperature=float(llm.get("temperature", 0.0)),
            ),
            crawl=CrawlSettings(
                max_pages=int(crawl.get("max_pages", 12)),
                page_chars=int(crawl.get("page_chars", 15000)),
                section_chars=int(crawl.get("section_chars", 30000)),
                timeout=float(crawl.get("timeout", 30)),
                delay=float(crawl.get("delay", 1.5)),
                browser=bool(crawl.get("browser", False)),
                respect_robots=bool(crawl.get("respect_robots", True)),
            ),
            browser=BrowserSettings.from_mapping(data.get("browser", {})),
            weights=weights,
            cache_dir=root / paths.get("cache_dir", "cache"),
            output_dir=root / paths.get("output_dir", "output"),
            system_prompt=root / paths.get("system_prompt", "prompts/system.md"),
            section_prompt=root / paths.get("section_prompt", "prompts/section.md"),
        )


def load_dotenv(path: Path) -> None:
    """Load simple KEY=VALUE lines into the environment without overriding existing variables."""
    if not path.exists():
        return
    for line in path.read_text(encoding="utf-8").splitlines():
        stripped = line.strip()
        if not stripped or stripped.startswith("#") or "=" not in stripped:
            continue
        key, value = stripped.split("=", 1)
        os.environ.setdefault(key.strip(), value.strip().strip("\"'"))
