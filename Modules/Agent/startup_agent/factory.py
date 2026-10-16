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
from .llm import CachedLLM, GeminiClient, LazyLLM, LLMClient, OpenAICompatibleClient
from .registry import PRHRegistry


def build_llm(settings: AgentSettings) -> LLMClient:
    llm = settings.llm
    if llm.provider == "gemini":
        return GeminiClient(api_key=llm.api_key(), model=llm.model, temperature=llm.temperature)
    if llm.provider in ("openai", "openai-compatible"):
        return OpenAICompatibleClient(endpoint=llm.endpoint, api_key=llm.api_key(), model=llm.model, temperature=llm.temperature)
    raise AgentError(f"unsupported [llm] provider: {llm.provider}")


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
    agent = StartupAgent(
        fetcher=fetcher,
        extractor=SectionExtractor(
            CachedLLM(LazyLLM(lambda: build_llm(settings), model=settings.llm.model), cache),
            PromptTemplates.load(settings.system_prompt, settings.section_prompt),
        ),
        loader=PageLoader(fetcher.fetch_text, cache=cache, robots=robots, today=today, page_chars=settings.crawl.page_chars),
        registry=PRHRegistry(fetcher.fetch_json, today=today),
        max_pages=settings.crawl.max_pages,
        section_chars=settings.crawl.section_chars,
        today=today,
    )
    return agent, fetcher
