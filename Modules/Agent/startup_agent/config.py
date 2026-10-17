"""Agent settings from config.toml, secrets from .env."""

from __future__ import annotations

import os
import tomllib
from dataclasses import dataclass, field, replace
from pathlib import Path
from typing import Any

from scraper.browser import BrowserSettings

from .errors import AgentError
from .judge import JudgeSettings
from .scoring import DEFAULT_WEIGHTS

DEFAULT_SECTION_GROUPS = (("A", "B", "H", "I"), ("C", "D", "E"), ("F", "G", "J"))


@dataclass(frozen=True, slots=True)
class LLMSettings:
    """One model the agent can use: a [llm.<name>] profile in config.toml (or [llm] itself, without profiles)."""

    provider: str
    model: str
    api_key_env: str
    endpoint: str
    temperature: float
    requests_per_minute: float  # shared by extraction, judge and search; 0 = no pacing
    thinking: str  # Gemini: "minimal" | "low" | "medium" | "high" | "" (model default)
    section_groups: tuple[tuple[str, ...], ...]  # sections extracted together in one call
    # openai-compatible providers (NVIDIA, ...):
    max_tokens: int | None = None  # answer budget per call; None = the endpoint's default
    timeout: float = 120.0  # seconds per call
    reasoning: bool | None = None  # Nemotron "thinking" (chat_template_kwargs.enable_thinking); None = not sent
    multimodal: bool = False  # the model also reads images (image_url content); Gemini always does
    name: str = ""  # the profile's name, e.g. "nvidia" or "gemini"

    @property
    def reads_images(self) -> bool:
        """Whether the scrape agent can hand images (and scanned pages) to the model."""
        return self.provider == "gemini" or self.multimodal

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
class PipelineSettings:
    limit: int  # startups researched per pipeline run
    max_age_days: int  # a startup the agent researched is left alone this many days, whatever the result
    discover: tuple[dict[str, Any], ...]  # discovery sources: {source, url, query, location, limit}


@dataclass(frozen=True, slots=True)
class AgentSettings:
    root: Path
    llm: LLMSettings
    crawl: CrawlSettings
    search: SearchSettings
    judge: JudgeSettings
    browser: BrowserSettings
    weights: dict[str, float]
    pipeline: PipelineSettings
    database: Path | None  # judge-approved entries are stored here; None = JSON files only
    cache_dir: Path
    output_dir: Path
    system_prompt: Path
    section_prompt: Path
    judge_prompt: Path
    llms: dict[str, LLMSettings] = field(default_factory=dict)  # every [llm.<name>] profile; ``llm`` is the one in use

    def with_llm(self, name: str | None) -> AgentSettings:
        """These settings with the named model profile in use; None or "" keeps the default."""
        if not name or name == self.llm.name:
            return self
        if name not in self.llms:
            raise AgentError(f"unknown model {name!r}: config.toml has {', '.join(self.llms) or 'no [llm.<name>] profiles'}")
        return replace(self, llm=self.llms[name])

    def gemini_llm(self) -> LLMSettings | None:
        """The Gemini profile (the one in use first), for Google Search grounding next to another model."""
        if self.llm.provider == "gemini":
            return self.llm
        return next((p for p in self.llms.values() if p.provider == "gemini"), None)

    @classmethod
    def load(cls, path: Path | None = None) -> AgentSettings:
        """Read ``path``, else $STARTUPGO_AGENT_CONFIG (e.g. refresh.py's runtime config), else config.toml next to the package."""
        path = path or Path(os.environ.get("STARTUPGO_AGENT_CONFIG") or DEFAULT_CONFIG)
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
        database: dict[str, Any] = data.get("database", {})
        pipeline: dict[str, Any] = data.get("pipeline", {})
        llms, default = _llm_profiles(llm)
        weights = {**DEFAULT_WEIGHTS, **{k: float(v) for k, v in data.get("weights", {}).items()}}
        if unknown := set(weights) - set(DEFAULT_WEIGHTS):
            raise AgentError(f"unknown [weights] criteria: {', '.join(sorted(unknown))}")

        return cls(
            root=root,
            llm=llms[default],
            llms=llms,
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
            pipeline=PipelineSettings(
                limit=int(pipeline.get("limit", 5)),
                max_age_days=int(pipeline.get("max_age_days", 30)),
                discover=tuple(_discover_source(d) for d in pipeline.get("discover", [])),
            ),
            # The Backend's STARTUPGO_DB override applies here too, so all modules use the same database.
            database=(Path(os.environ.get("STARTUPGO_DB") or root / database.get("path", "../../DB/startupgo_unified.db"))
                      if database.get("store", True) else None),
            cache_dir=root / paths.get("cache_dir", "cache"),
            output_dir=root / paths.get("output_dir", "output"),
            system_prompt=root / paths.get("system_prompt", "prompts/system.md"),
            section_prompt=root / paths.get("section_prompt", "prompts/section.md"),
            judge_prompt=root / paths.get("judge_prompt", "prompts/judge.md"),
        )


def _llm_profiles(llm: dict[str, Any]) -> tuple[dict[str, LLMSettings], str]:
    """Model profiles and the default's name. Keys on [llm] are shared; each [llm.<name>] table adds or overrides keys.

    Without profile tables, [llm] itself is the one profile, named after its provider.
    """
    shared = {k: v for k, v in llm.items() if not isinstance(v, dict)}
    tables = {k: v for k, v in llm.items() if isinstance(v, dict)} or {_provider_name(shared): {}}
    profiles = {name: _llm_settings(name, {**shared, **table}) for name, table in tables.items()}
    default = str(shared.get("default") or next(iter(profiles)))
    if default not in profiles:
        raise AgentError(f"[llm] default = {default!r} is not a profile: config.toml has {', '.join(profiles)}")
    return profiles, default


def _provider_name(llm: dict[str, Any]) -> str:
    provider = str(llm.get("provider", "gemini")).casefold()
    return "gemini" if provider == "gemini" else "nvidia" if "nvidia" in str(llm.get("endpoint", "")) else provider


def _llm_settings(name: str, llm: dict[str, Any]) -> LLMSettings:
    return LLMSettings(
        provider=str(llm.get("provider", "gemini")).casefold(),
        model=str(llm.get("model", "gemini-3.8-flash")),
        api_key_env=str(llm.get("api_key_env", "GEMINI_API_KEY")),
        endpoint=str(llm.get("endpoint", "")),
        temperature=float(llm.get("temperature", 0.0)),
        requests_per_minute=float(llm.get("requests_per_minute", 10)),
        thinking=str(llm.get("thinking", "minimal")).casefold(),
        section_groups=_section_groups(llm.get("section_groups", DEFAULT_SECTION_GROUPS)),
        max_tokens=int(llm["max_tokens"]) if llm.get("max_tokens") else None,
        timeout=float(llm.get("timeout", 120)),
        reasoning=bool(llm["reasoning"]) if "reasoning" in llm else None,
        multimodal=bool(llm.get("multimodal", False)),
        name=name,
    )


def _discover_source(source: Any) -> dict[str, Any]:
    if not isinstance(source, dict) or not (source.get("url") or source.get("query")):
        raise AgentError(f"[pipeline] discover entries need a url or a query, got {source!r}")
    if (name := source.get("source", "wellfound")) not in ("wellfound", "generic", "osm"):
        raise AgentError(f"[pipeline] discover source must be wellfound, generic or osm, got {name!r}")
    return {"source": name, "url": source.get("url"), "query": source.get("query"),
            "location": str(source.get("location", "")), "limit": int(source.get("limit", 10))}


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
