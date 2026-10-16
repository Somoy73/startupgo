"""Command-line interface for the startup scraper."""

from __future__ import annotations

import argparse
import logging
import sys
from pathlib import Path
from typing import Sequence

from .errors import ScraperError
from .fetchers import PublicPageFetcher
from .output import LeadOutputWriter
from .service import StartupScraper

LOGGER = logging.getLogger("startupgo.scraper")
SOURCES = ("generic", "linkedin", "glassdoor", "wellfound", "osm")


def parse_args(argv: Sequence[str]) -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--source", choices=SOURCES, default="generic")
    parser.add_argument("--url", help="Public directory/search URL to parse")
    parser.add_argument("--query", help="Search term for the osm source")
    parser.add_argument("--location", default="", help="Optional location for the osm source")
    parser.add_argument("--limit", type=int, default=50)
    parser.add_argument("--delay", type=float, default=1.0, help="Minimum seconds between requests")
    parser.add_argument("--timeout", type=float, default=20.0)
    parser.add_argument("--browser", action="store_true", help="Render public pages with Selenium")
    parser.add_argument("--format", choices=("json", "csv"), default="json", dest="output_format")
    parser.add_argument("--output", type=Path)
    return parser.parse_args(argv)


def main(argv: Sequence[str] | None = None) -> int:
    args = parse_args(argv or sys.argv[1:])
    if args.limit < 1:
        LOGGER.error("--limit must be greater than zero")
        return 2
    fetcher = PublicPageFetcher(timeout=args.timeout, delay=args.delay, browser=args.browser)
    try:
        leads = StartupScraper(fetcher).collect(
            source=args.source,
            url=args.url,
            query=args.query,
            location=args.location,
            limit=args.limit,
        )
        LeadOutputWriter().write(leads, output=args.output, output_format=args.output_format)
    except ScraperError as exc:
        LOGGER.error("%s", exc)
        return 1
    finally:
        fetcher.close()
    return 0
