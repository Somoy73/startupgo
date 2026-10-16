"""Compatibility entrypoint for the modular StartupGo scraper."""

from scraper.adapters import (
    GenericDirectoryAdapter,
    NetworkDirectoryAdapter,
    OpenStreetMapAdapter,
    SourceAdapter,
    build_osm_url,
)
from scraper.errors import ScraperError
from scraper.fetchers import PublicPageFetcher
from scraper.models import StartupLead
from scraper.service import StartupScraper
from scraper.utils import absolute_url, clean, deduplicate
from scraper.cli import main

__all__ = [
    "GenericDirectoryAdapter",
    "NetworkDirectoryAdapter",
    "OpenStreetMapAdapter",
    "PublicPageFetcher",
    "ScraperError",
    "SourceAdapter",
    "StartupLead",
    "StartupScraper",
    "absolute_url",
    "build_osm_url",
    "clean",
    "deduplicate",
    "main",
]


if __name__ == "__main__":
    raise SystemExit(main())
