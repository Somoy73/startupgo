"""Builds configured scraper components."""

from __future__ import annotations

from .config import AppSettings
from .fetchers import PublicPageFetcher


def create_fetcher(settings: AppSettings) -> PublicPageFetcher:
    """A fetcher using the configured pacing and browser; call ``close()`` when done."""
    return PublicPageFetcher(
        timeout=settings.scraper.timeout,
        delay=settings.scraper.delay,
        browser=settings.scraper.browser,
        browser_settings=settings.browser,
    )
