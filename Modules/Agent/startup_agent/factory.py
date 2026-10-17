"""Builds a configured agent from settings."""

from __future__ import annotations

from datetime import date

from scraper.fetchers import PublicPageFetcher

from .agent import StartupAgent
from .cache import JsonCache
from .config import AgentSettings, LLMSettings
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
from .retrievals import RetrievalLog
from .search import BraveSearch, CachedSearch, GeminiGoogleSearch, WebSearch, resolve_redirect


def build_gemini_session(llm: LLMSettings, stats: UsageStats) -> GeminiSession:
    """One paced Gemini client for extraction, judge and search (the key is read on first use)."""
    rpm = llm.requests_per_minute
    return GeminiSession(
        lambda: gemini_client(llm.api_key()),
        stats=stats,
        limiter=RateLimiter(rpm) if rpm > 0 else None,
        thinking=llm.thinking,
    )


def build_llm(settings: AgentSettings, session: GeminiSession | None, stats: UsageStats | None = None) -> LLMClient:
    llm = settings.llm
    if llm.provider == "gemini" and session:
        return GeminiClient(session, model=llm.model, temperature=llm.temperature)
    if llm.provider in ("openai", "openai-compatible"):
        # Nemotron models think before answering unless told not to; other endpoints never see the key.
        extra_body = {"chat_template_kwargs": {"enable_thinking": llm.reasoning}} if llm.reasoning is not None else {}
        rpm = llm.requests_per_minute
        return LazyLLM(
            lambda: OpenAICompatibleClient(
                endpoint=llm.endpoint,
                api_key=llm.api_key(),
                model=llm.model,
                temperature=llm.temperature,
                timeout=llm.timeout,
                max_tokens=llm.max_tokens,
                extra_body=extra_body,
                multimodal=llm.multimodal,
                limiter=RateLimiter(rpm) if rpm > 0 else None,
                stats=stats,
            ),
            model=llm.model,
        )
    raise AgentError(f"unsupported [llm] provider: {llm.provider}")


def build_search(settings: AgentSettings, session: GeminiSession | None, *, user_agent: str, stats: UsageStats | None = None) -> WebSearch | None:
    """The [search] provider. Gemini's Google Search also works next to another model (NVIDIA): it then uses the
    [llm.gemini] profile's key and model, in a session of its own."""
    search = settings.search
    if search.provider == "none":
        return None
    if search.provider == "gemini":
        gemini = settings.gemini_llm()
        if gemini is None:
            raise AgentError('[search] provider "gemini" needs a Gemini model profile ([llm.gemini] in config.toml) for its key')
        if session is None or settings.llm.provider != "gemini":
            session = build_gemini_session(gemini, stats or UsageStats())
        return GeminiGoogleSearch(
            session,
            model=gemini.model,
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
    log = RetrievalLog()
    session = build_gemini_session(settings.llm, stats) if settings.llm.provider == "gemini" else None
    searcher = build_search(settings, session, user_agent=fetcher.user_agent, stats=stats)
    agent = StartupAgent(
        fetcher=fetcher,
        extractor=SectionExtractor(
            CachedLLM(build_llm(settings, session, stats), cache, stats=stats),
            PromptTemplates.load(settings.system_prompt, settings.section_prompt),
        ),
        loader=PageLoader(fetcher.fetch_text, cache=cache, robots=robots, today=today, page_chars=settings.crawl.page_chars, log=log),
        registry=PRHRegistry(fetcher.fetch_json, today=today),
        max_pages=settings.crawl.max_pages,
        section_chars=settings.crawl.section_chars,
        searcher=CachedSearch(searcher, cache, stats=stats, log=log) if searcher else None,
        search_queries=settings.search.queries,
        max_search_pages=settings.search.max_pages,
        results_per_query=settings.search.results_per_query,
        section_groups=settings.llm.section_groups,
        usage=stats,
        today=today,
    )
    agent.log = log
    return agent, fetcher
