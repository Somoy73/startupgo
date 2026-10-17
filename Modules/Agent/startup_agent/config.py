"""Agent settings from config.toml, secrets from .env."""

from __future__ import annotations

import os
import tomllib
from dataclasses import dataclass
from pathlib import Path
from typing import Any

from scraper.browser import BrowserSettings

from .errors import AgentError
from .judge import JudgeSettings
from .scoring import DEFAULT_WEIGHTS

DEFAULT_SECTION_GROUPS = (("A", "B", "H", "I"), ("C", "D", "E"), ("F", "G", "J"))


@dataclass(frozen=True, slots=True)
class LLMSettings:
    provider: str
    model: str
    api_key_env: str
    endpoint: str
    temperature: float
    requests_per_minute: float  # shared by extraction, judge and search; 0 = no pacing
    thinking: str  # "minimal" | "low" | "medium" | "high" | "" (model default)
    section_groups: tuple[tuple[str, ...], ...]  # sections extracted together in one call

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


# config.toml next to the package, so commands work from any directory.
DEFAULT_CONFIG = Path(__file__).resolve().parents[1] / "config.toml"

DEFAULT_SEARCH_QUERIES = (
    '"{name}" startup funding investment',
    '"{name}" pilot partnership customers',
    '"{name}" news award',
)


@dataclass(frozen=True, slots=True)
class SearchSettings:
    provider: str  # "gemini", "brave" or "none"
    api_key_env: str  # brave only; gemini uses the [llm] key
    queries: tuple[str, ...]  # templates with {name} and {domain}
    results_per_query: int
    max_pages: int  # search-result pages fetched per startup

    def api_key(self) -> str:
        key = os.getenv(self.api_key_env, "").strip()
        if not key:
            raise AgentError(f"missing search credential: set {self.api_key_env} in .env")
        return key


@dataclass(frozen=True, slots=True)
class AgentSettings:
    root: Path
    llm: LLMSettings
    crawl: CrawlSettings
    search: SearchSettings
    judge: JudgeSettings
    browser: BrowserSettings
    weights: dict[str, float]
    cache_dir: Path
    output_dir: Path
    system_prompt: Path
    section_prompt: Path
    judge_prompt: Path

    @classmethod
    def load(cls, path: Path | None = None) -> AgentSettings:
        path = path or DEFAULT_CONFIG
        root = path.resolve().parent
        load_dotenv(root / ".env")
        try:
            data = tomllib.loads(path.read_text(encoding="utf-8"))
        except (OSError, tomllib.TOMLDecodeError) as exc:
            raise AgentError(f"could not read configuration {path}: {exc}") from exc

        llm: dict[str, Any] = data.get("llm", {})
        crawl: dict[str, Any] = data.get("crawl", {})
        search: dict[str, Any] = data.get("search", {})
        judge: dict[str, Any] = data.get("judge", {})
        judge_defaults = JudgeSettings()
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
                requests_per_minute=float(llm.get("requests_per_minute", 10)),
                thinking=str(llm.get("thinking", "minimal")).casefold(),
                section_groups=_section_groups(llm.get("section_groups", DEFAULT_SECTION_GROUPS)),
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
            search=SearchSettings(
                provider=str(search.get("provider", "gemini")).casefold(),
                api_key_env=str(search.get("api_key_env", "BRAVE_API_KEY")),
                queries=tuple(search.get("queries", DEFAULT_SEARCH_QUERIES)),
                results_per_query=int(search.get("results_per_query", 5)),
                max_pages=int(search.get("max_pages", 6)),
            ),
            judge=JudgeSettings(
                max_research_rounds=int(judge.get("max_research_rounds", judge_defaults.max_research_rounds)),
                max_evaluation_rounds=int(judge.get("max_evaluation_rounds", judge_defaults.max_evaluation_rounds)),
                check_support=bool(judge.get("check_support", judge_defaults.check_support)),
                max_rejected_per_section=int(judge.get("max_rejected_per_section", judge_defaults.max_rejected_per_section)),
                min_confidence=float(judge.get("min_confidence", judge_defaults.min_confidence)),
                required_fields=tuple(judge.get("required_fields", judge_defaults.required_fields)),
            ),
            browser=BrowserSettings.from_mapping(data.get("browser", {})),
            weights=weights,
            cache_dir=root / paths.get("cache_dir", "cache"),
            output_dir=root / paths.get("output_dir", "output"),
            system_prompt=root / paths.get("system_prompt", "prompts/system.md"),
            section_prompt=root / paths.get("section_prompt", "prompts/section.md"),
            judge_prompt=root / paths.get("judge_prompt", "prompts/judge.md"),
        )


def _section_groups(groups: Any) -> tuple[tuple[str, ...], ...]:
    """Validate [llm] section_groups: every section A-J exactly once."""
    from .spec import SECTIONS

    parsed = tuple(tuple(str(s).upper() for s in group) for group in groups)
    flat = [s for group in parsed for s in group]
    if sorted(flat) != sorted(SECTIONS) or any(not group for group in parsed):
        raise AgentError(f"[llm] section_groups must list every section {', '.join(SECTIONS)} exactly once, got {parsed}")
    return parsed


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
