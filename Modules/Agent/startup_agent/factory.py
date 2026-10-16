"""Builds a configured agent from settings."""

from __future__ import annotations

from datetime import date

from scraper.fetchers import PublicPageFetcher

from .agent import StartupAgent
from .cache import JsonCache
from .config import AgentSettings
from .crawler import PageLoader, fetch_robots_txt
from .documents import RobotsPolicy
from .errors import AgentError
from .extraction import PromptTemplates, SectionExtractor
from .judge import Judge
from .llm import (
    CachedLLM,
    GeminiClient,
    GeminiSession,
    LazyLLM,
    LLMClient,
    OpenAICompatibleClient,
    RateLimiter,
    UsageStats,
    gemini_client,
)
from .registry import PRHRegistry
from .search import BraveSearch, CachedSearch, GeminiGoogleSearch, WebSearch, resolve_redirect


def build_gemini_session(settings: AgentSettings, stats: UsageStats) -> GeminiSession:
    """One paced Gemini client for extraction, judge and search (the key is read on first use)."""
    rpm = settings.llm.requests_per_minute
    return GeminiSession(
        lambda: gemini_client(settings.llm.api_key()),
        stats=stats,
        limiter=RateLimiter(rpm) if rpm > 0 else None,
        thinking=settings.llm.thinking,
    )


def build_llm(settings: AgentSettings, session: GeminiSession | None) -> LLMClient:
    llm = settings.llm
    if llm.provider == "gemini" and session:
        return GeminiClient(session, model=llm.model, temperature=llm.temperature)
    if llm.provider in ("openai", "openai-compatible"):
        return LazyLLM(
            lambda: OpenAICompatibleClient(endpoint=llm.endpoint, api_key=llm.api_key(), model=llm.model, temperature=llm.temperature),
            model=llm.model,
        )
    raise AgentError(f"unsupported [llm] provider: {llm.provider}")


def build_search(settings: AgentSettings, session: GeminiSession | None, *, user_agent: str) -> WebSearch | None:
    search = settings.search
    if search.provider == "none":
        return None
    if search.provider == "gemini":
        if session is None:
            raise AgentError('[search] provider "gemini" needs [llm] provider "gemini" (it uses the same key)')
        return GeminiGoogleSearch(
            session,
            model=settings.llm.model,
            resolve=lambda url: resolve_redirect(url, user_agent=user_agent),
        )
    if search.provider == "brave":
        return BraveSearch(api_key=search.api_key())
    raise AgentError(f"unsupported [search] provider: {search.provider}")


def build_judge(settings: AgentSettings, agent: StartupAgent) -> Judge:
    """The judge shares the agent's (cached) LLM for its quote-support check."""
    try:
        prompt = settings.judge_prompt.read_text(encoding="utf-8").strip()
    except OSError as exc:
        raise AgentError(f"could not read judge prompt {settings.judge_prompt}: {exc}") from exc
    return Judge(
        settings.judge,
        llm=agent.extractor.llm,
        system_prompt=prompt,
        can_search=lambda: agent.searcher is not None and agent.searcher.available,
        weights=settings.weights,
    )


def build_agent(settings: AgentSettings, *, refresh: bool = False) -> tuple[StartupAgent, PublicPageFetcher]:
    """Returns the agent and its fetcher; call ``fetcher.close()`` when done (it may hold a browser)."""
    today = date.today().isoformat()
    cache = JsonCache(settings.cache_dir, read=not refresh)
    fetcher = PublicPageFetcher(
        timeout=settings.crawl.timeout,
        delay=settings.crawl.delay,
        browser=settings.crawl.browser,
        browser_settings=settings.browser,
    )
    robots = (
        RobotsPolicy(lambda url: fetch_robots_txt(url, user_agent=fetcher.user_agent), fetcher.user_agent)
        if settings.crawl.respect_robots
        else None
    )
    stats = UsageStats()
    session = build_gemini_session(settings, stats) if settings.llm.provider == "gemini" else None
    searcher = build_search(settings, session, user_agent=fetcher.user_agent)
    agent = StartupAgent(
        fetcher=fetcher,
        extractor=SectionExtractor(
            CachedLLM(build_llm(settings, session), cache, stats=stats),
            PromptTemplates.load(settings.system_prompt, settings.section_prompt),
        ),
        loader=PageLoader(fetcher.fetch_text, cache=cache, robots=robots, today=today, page_chars=settings.crawl.page_chars),
        registry=PRHRegistry(fetcher.fetch_json, today=today),
        max_pages=settings.crawl.max_pages,
        section_chars=settings.crawl.section_chars,
        searcher=CachedSearch(searcher, cache, stats=stats) if searcher else None,
        search_queries=settings.search.queries,
        max_search_pages=settings.search.max_pages,
        results_per_query=settings.search.results_per_query,
        section_groups=settings.llm.section_groups,
        usage=stats,
        today=today,
    )
    return agent, fetcher
