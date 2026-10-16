"""Command-line interface for the startup scraper.

Pacing and browser options come from config.toml; flags given on the command line override them.
"""

from __future__ import annotations

import argparse
import logging
import sys
from collections.abc import Sequence
from dataclasses import replace
from pathlib import Path
from typing import Any

from .config import AppSettings
from .errors import ScraperError
from .factory import create_fetcher
from .output import LeadOutputWriter
from .service import StartupScraper

LOGGER = logging.getLogger("startupgo.scraper")
SOURCES = ("generic", "linkedin", "glassdoor", "wellfound", "osm")


def parse_args(argv: Sequence[str]) -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--config", type=Path, help="Settings file (default: config.toml next to the package, if present)")
    parser.add_argument("--source", choices=SOURCES, default="generic")
    parser.add_argument("--url", help="Public directory/search URL to parse")
    parser.add_argument("--query", help="Search term for the osm source")
    parser.add_argument("--location", default="", help="Optional location for the osm source")
    parser.add_argument("--limit", type=int, default=50)
    parser.add_argument("--format", choices=("json", "csv"), default="json", dest="output_format")
    parser.add_argument("--output", type=Path)

    # Overrides for config.toml; None means "use the configured value".
    parser.add_argument("--delay", type=float, help="Minimum seconds between requests")
    parser.add_argument("--timeout", type=float)
    parser.add_argument("--browser", action=argparse.BooleanOptionalAction, help="Render public pages with Chrome")
    parser.add_argument("--driver", choices=("undetected", "selenium"), help="Chrome driver for browser mode")
    parser.add_argument("--stealth", action=argparse.BooleanOptionalAction, help="selenium-stealth fingerprint masking")
    parser.add_argument("--headed", action="store_true", default=None, help="Show the browser window")
    parser.add_argument("--chrome-version", type=int, help="Chrome major version for undetected-chromedriver")
    return parser.parse_args(argv)


def build_settings(args: argparse.Namespace) -> AppSettings:
    """Configured settings with command-line overrides applied."""
    settings = AppSettings.load(args.config)

    def given(**values: Any) -> dict[str, Any]:
        return {key: value for key, value in values.items() if value is not None}

    return AppSettings(
        scraper=replace(settings.scraper, **given(timeout=args.timeout, delay=args.delay, browser=args.browser)),
        browser=replace(
            settings.browser,
            **given(
                driver=args.driver,
                stealth=args.stealth,
                headless=False if args.headed else None,
                chrome_version=args.chrome_version,
            ),
        ),
    )


def main(argv: Sequence[str] | None = None) -> int:
    args = parse_args(argv if argv is not None else sys.argv[1:])
    if args.limit < 1:
        LOGGER.error("--limit must be greater than zero")
        return 2
    try:
        fetcher = create_fetcher(build_settings(args))
    except ScraperError as exc:
        LOGGER.error("%s", exc)
        return 1
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
