"""Source-specific startup lead adapters."""

from __future__ import annotations

import json
from abc import ABC, abstractmethod
from typing import Any, Protocol
from urllib.parse import quote_plus

from bs4 import BeautifulSoup

from .errors import ScraperError
from .models import StartupLead
from .utils import absolute_url, clean, deduplicate


class PageFetcher(Protocol):
    def fetch_text(self, url: str) -> str: ...
    def fetch_json(self, url: str) -> Any: ...


class SourceAdapter(ABC):
    """Extension point for one public startup source."""

    name = "generic"

    @abstractmethod
    def collect(self, *, url: str, fetcher: PageFetcher, limit: int) -> list[StartupLead]:
        """Collect and normalize leads from a source."""


class GenericDirectoryAdapter(SourceAdapter):
    """Parse common card/list markup and JSON-LD from a directory page."""

    name = "generic"

    def collect(self, *, url: str, fetcher: PageFetcher, limit: int) -> list[StartupLead]:
        document = BeautifulSoup(fetcher.fetch_text(url), "html.parser")
        leads = self._from_json_ld(document, url)
        leads.extend(self._from_cards(document, url))
        return deduplicate(leads)[:limit]

    def _from_json_ld(self, document: BeautifulSoup, url: str) -> list[StartupLead]:
        leads: list[StartupLead] = []
        for script in document.select('script[type="application/ld+json"]'):
            try:
                payload = json.loads(script.string or "")
            except json.JSONDecodeError:
                continue
            items = payload if isinstance(payload, list) else [payload]
            for item in items:
                if not isinstance(item, dict) or not item.get("name"):
                    continue
                address = item.get("address") or {}
                leads.append(
                    StartupLead(
                        name=clean(item.get("name")),
                        source=self.name,
                        source_url=absolute_url(item.get("url") or url, url),
                        description=clean(item.get("description")),
                        website=clean(item.get("url")) if item.get("@type") == "Organization" else "",
                        city=clean(address.get("addressLocality")),
                        country=clean(address.get("addressCountry")),
                    )
                )
        return leads

    def _from_cards(self, document: BeautifulSoup, url: str) -> list[StartupLead]:
        leads: list[StartupLead] = []
        selectors = (
            "[data-testid*='company'], [data-testid*='startup'], "
            "[class*='company-card'], [class*='startup-card'], article, li"
        )
        for card in document.select(selectors):
            link = card.select_one("a[href]")
            name_node = card.select_one("h1, h2, h3, h4, [class*='name'], [class*='title']")
            name = clean(name_node.get_text(" ", strip=True) if name_node else "")
            if not name and link:
                name = clean(link.get_text(" ", strip=True))
            if not name or len(name) > 160:
                continue
            text = clean(card.get_text(" ", strip=True))
            leads.append(
                StartupLead(
                    name=name,
                    source=self.name,
                    source_url=absolute_url(link["href"] if link else url, url),
                    tagline=text[:300],
                    description=text[:1000],
                )
            )
        return leads


class NetworkDirectoryAdapter(GenericDirectoryAdapter):
    """Apply generic public-page parsing with an explicit source label."""

    def __init__(self, source_name: str):
        self.name = source_name


class OpenStreetMapAdapter(SourceAdapter):
    """Find publicly listed places matching a query via Nominatim."""

    name = "osm"

    def collect(self, *, url: str, fetcher: PageFetcher, limit: int) -> list[StartupLead]:
        places = fetcher.fetch_json(url)
        if not isinstance(places, list):
            raise ScraperError("OpenStreetMap returned an unexpected response")

        leads = []
        for place in places[:limit]:
            address = place.get("address") or {}
            name = clean(place.get("name") or place.get("display_name", "").split(",")[0])
            if not name:
                continue
            leads.append(
                StartupLead(
                    name=name,
                    source=self.name,
                    source_url=f"https://www.openstreetmap.org/{place.get('osm_type', 'node')}/{place.get('osm_id')}",
                    description=clean(place.get("display_name")),
                    city=clean(address.get("city") or address.get("town") or address.get("village")),
                    country=clean(address.get("country")),
                    latitude=float(place["lat"]) if place.get("lat") else None,
                    longitude=float(place["lon"]) if place.get("lon") else None,
                    external_id=str(place.get("osm_id", "")),
                )
            )
        return deduplicate(leads)


def build_osm_url(query: str, location: str = "") -> str:
    search = f"{query} {location}".strip()
    return (
        "https://nominatim.openstreetmap.org/search?"
        f"q={quote_plus(search)}&format=jsonv2&addressdetails=1&limit=50"
    )
