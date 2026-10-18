"""Loading pages through the scraper's fetcher with caching, robots.txt and same-site link following."""

from __future__ import annotations

from collections.abc import Callable
from urllib.error import HTTPError, URLError
from urllib.parse import urlsplit
from urllib.request import Request, urlopen

from scraper.errors import ScraperError

from .cache import JsonCache
from .documents import Link, RobotsPolicy, SourceDocument, host, html_to_document, rank_links
from .retrievals import Retrieval, RetrievalLog, Status
from .vocab import SourceType


class PageSkipped(Exception):
    """A page was deliberately not fetched (e.g. disallowed by robots.txt)."""


def fetch_robots_txt(url: str, *, user_agent: str, timeout: float = 10) -> str | None:
    """robots.txt body, or None when it can't be read (treated as allow-all)."""
    try:
        with urlopen(Request(url, headers={"User-Agent": user_agent}), timeout=timeout) as response:
            return response.read().decode("utf-8", "replace")
    except (HTTPError, URLError, TimeoutError, ValueError):
        return None


def normalize_website(url: str) -> str:
    url = url.strip()
    if "://" not in url:
        url = f"https://{url}"
    parts = urlsplit(url)
    return f"{parts.scheme}://{parts.netloc}{parts.path.rstrip('/') or '/'}"


class PageLoader:
    def __init__(
        self,
        fetch_text: Callable[[str], str],
        *,
        cache: JsonCache,
        robots: RobotsPolicy | None,
        today: str,
        page_chars: int,
        log: RetrievalLog | None = None,
    ):
        self._fetch_text = fetch_text
        self._cache = cache
        self._robots = robots
        self._today = today
        self._page_chars = page_chars
        self.log = log

    def load(
        self, url: str, *, source_type: SourceType, is_homepage: bool = False, readable: bool = False
    ) -> tuple[SourceDocument, list[Link]]:
        cached = self._cache.get("pages", url)
        try:
            if cached:
                html, retrieved_at = cached["html"], cached["retrieved_at"]
            else:
                if self._robots and not self._robots.allowed(url):
                    raise PageSkipped(f"{url} is disallowed by robots.txt")
                html, retrieved_at = self._fetch_text(url), self._today
                self._cache.put("pages", url, {"url": url, "retrieved_at": retrieved_at, "html": html})
        except Exception as exc:  # recorded, then raised to the caller as before
            self._record(url, source_type, "skipped" if isinstance(exc, PageSkipped) else "error", str(exc))
            raise
        self._record(url, source_type, "cached" if cached else "ok")
        return html_to_document(
            url, html, source_type=source_type, retrieved_at=retrieved_at, max_chars=self._page_chars, is_homepage=is_homepage,
            readable=readable,
        )

    def _record(self, url: str, source_type: str, status: Status, detail: str | None = None) -> None:
        if self.log is not None:
            self.log.add(Retrieval("page", status, url=url, source_type=source_type, detail=detail, retrieved_at=self._today))


def crawl_site(loader: PageLoader, website: str, *, max_pages: int, errors: list[dict[str, str]]) -> list[SourceDocument]:
    """Homepage plus the most section-relevant same-site pages it links to."""
    home, links = loader.load(website, source_type="website", is_homepage=True)
    documents = [home]
    for url in rank_links(links, host(website), exclude={website}):
        if len(documents) >= max_pages:
            break
        try:
            documents.append(loader.load(url, source_type="website")[0])
        except (ScraperError, PageSkipped) as exc:
            errors.append({"stage": "crawl", "url": url, "message": str(exc)})
    return documents
