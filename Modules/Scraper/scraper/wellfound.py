"""Wellfound startup discovery from public startup collection pages.

Collection pages such as ``/startups/industry/clean-technology`` or
``/startups/location/finland`` embed their results as Apollo GraphQL state in
the Next.js ``__NEXT_DATA__`` script. Parsing that payload is more stable than
scraping the rendered markup.

Only collection pages are used: robots.txt disallows ``/search``, and company
profile pages sit behind a bot check.
"""

from __future__ import annotations

import json
import re
from dataclasses import dataclass
from typing import Any
from urllib.parse import parse_qs, urlencode, urlsplit, urlunsplit

from .adapters import PageFetcher, SourceAdapter
from .errors import ScraperError
from .models import StartupLead
from .utils import clean, deduplicate

_NEXT_DATA = re.compile(r'<script id="__NEXT_DATA__"[^>]*>(.*?)</script>', re.DOTALL)
_HOSTS = {"wellfound.com", "www.wellfound.com"}
_RESULTS_PREFIX = "seoLandingPageStartupSearchResults"


@dataclass(slots=True)
class WellfoundPage:
    leads: list[StartupLead]
    page_count: int
    total_startups: int


class WellfoundAdapter(SourceAdapter):
    name = "wellfound"

    def collect(self, *, url: str, fetcher: PageFetcher, limit: int) -> list[StartupLead]:
        base_url, page = self._validate(url)
        leads: list[StartupLead] = []
        while len(leads) < limit:
            page_url = self.page_url(base_url, page)
            result = self.parse(fetcher.fetch_text(page_url), page_url)
            leads.extend(result.leads)
            if not result.leads or page >= result.page_count:
                break
            page += 1
        return deduplicate(leads)[:limit]

    @staticmethod
    def page_url(base_url: str, page: int) -> str:
        return base_url if page == 1 else f"{base_url}?{urlencode({'page': page})}"

    @staticmethod
    def _validate(url: str) -> tuple[str, int]:
        parts = urlsplit(url)
        if parts.scheme != "https" or parts.hostname not in _HOSTS or not parts.path.startswith("/startups/"):
            raise ScraperError(
                "Wellfound discovery takes a startup collection URL such as "
                "https://wellfound.com/startups/industry/clean-technology or "
                "https://wellfound.com/startups/location/finland "
                "(/search is disallowed by robots.txt; company pages are behind a bot check)"
            )
        page = int(parse_qs(parts.query).get("page", ["1"])[0] or 1)
        return urlunsplit(("https", "wellfound.com", parts.path.rstrip("/"), "", "")), max(1, page)

    def parse(self, html: str, page_url: str) -> WellfoundPage:
        match = _NEXT_DATA.search(html)
        if not match:
            raise ScraperError(f"{page_url} has no __NEXT_DATA__ payload; the page layout may have changed")
        try:
            apollo: dict[str, Any] = json.loads(match.group(1))["props"]["pageProps"]["apolloState"]["data"]
            talent = apollo["ROOT_QUERY"]["talent"]
        except (json.JSONDecodeError, KeyError, TypeError) as exc:
            raise ScraperError(f"{page_url} has an unexpected __NEXT_DATA__ structure") from exc

        key, results = next(((k, v) for k, v in talent.items() if k.startswith(_RESULTS_PREFIX)), ("", None))
        if not results:
            return WellfoundPage(leads=[], page_count=0, total_startups=0)
        # Unknown collections redirect to a generic list; its results key won't name the requested slug.
        slug = urlsplit(page_url).path.rstrip("/").rsplit("/", 1)[-1]
        if f'"{slug}"' not in key:
            raise ScraperError(f"Wellfound has no collection at {page_url} (it redirected to a generic list)")

        def resolve(ref: Any) -> dict[str, Any]:
            return apollo.get(ref.get("__ref", ""), {}) if isinstance(ref, dict) else {}

        leads = [
            self._lead(record, resolve, page_url)
            for record in (resolve(ref) for ref in results.get("startups", []))
            if record.get("name")
        ]
        return WellfoundPage(
            leads=leads,
            page_count=int(results.get("pageCount") or 1),
            total_startups=int(results.get("totalStartupCount") or len(leads)),
        )

    def _lead(self, record: dict[str, Any], resolve, page_url: str) -> StartupLead:
        def tag_names(key: str) -> list[str]:
            return [clean(resolve(ref).get("displayName")) for ref in record.get(key, []) if resolve(ref)]

        stage = next(
            (
                clean(badge.get("label"))
                for badge in map(resolve, record.get("badges", []))
                if badge.get("name") == "COMPANY_STAGE_BADGE"
            ),
            "",
        )
        return StartupLead(
            name=clean(record["name"]),
            source=self.name,
            # Provenance: the collection page the data was read from.
            source_url=page_url,
            tagline=clean(record.get("highConcept")),
            description=clean(record.get("description")),
            website=clean(record.get("companyUrl")),
            # Wellfound location tags mix cities and countries without saying which is which.
            location=", ".join(tag_names("locationTaggings")),
            sector=", ".join(tag_names("marketTaggings")[:3]),
            stage=stage,
            external_id=clean(record.get("slug")),
        )
