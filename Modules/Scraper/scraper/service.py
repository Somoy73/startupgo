"""Application service coordinating source adapters and transport."""

from __future__ import annotations

from .adapters import (
    GenericDirectoryAdapter,
    NetworkDirectoryAdapter,
    OpenStreetMapAdapter,
    PageFetcher,
    SourceAdapter,
    build_osm_url,
)
from .errors import ScraperError
from .models import StartupLead


class StartupScraper:
    """Coordinate source selection without coupling adapters to the CLI."""

    def __init__(self, fetcher: PageFetcher, adapters: dict[str, SourceAdapter] | None = None):
        self.fetcher = fetcher
        self.adapters = adapters or {
            "generic": GenericDirectoryAdapter(),
            "linkedin": NetworkDirectoryAdapter("linkedin"),
            "glassdoor": NetworkDirectoryAdapter("glassdoor"),
            "wellfound": NetworkDirectoryAdapter("wellfound"),
            "osm": OpenStreetMapAdapter(),
        }

    def collect(
        self,
        *,
        source: str,
        url: str | None = None,
        query: str | None = None,
        location: str = "",
        limit: int = 50,
    ) -> list[StartupLead]:
        adapter = self.adapters.get(source)
        if adapter is None:
            raise ScraperError(f"unsupported source: {source}")
        if source == "osm":
            if not query:
                raise ScraperError("--query is required for the osm source")
            target_url = build_osm_url(query, location)
        else:
            if not url:
                raise ScraperError("--url is required for this source")
            target_url = url
        return adapter.collect(url=target_url, fetcher=self.fetcher, limit=limit)
