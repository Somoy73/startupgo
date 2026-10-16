"""Domain models used by all scraper adapters."""

from __future__ import annotations

import hashlib
from dataclasses import dataclass


@dataclass(slots=True)
class StartupLead:
    """A normalized, source-independent candidate startup."""

    name: str
    source: str
    source_url: str
    tagline: str = ""
    description: str = ""
    website: str = ""
    country: str = ""
    city: str = ""
    # Free-form location when a source doesn't say whether it is a city or a country.
    location: str = ""
    sector: str = ""
    stage: str = ""
    latitude: float | None = None
    longitude: float | None = None
    external_id: str = ""

    def key(self) -> str:
        """Return a stable key used to remove duplicate leads."""

        value = self.website or self.source_url or self.name
        return hashlib.sha256(value.strip().lower().encode("utf-8")).hexdigest()[:16]
