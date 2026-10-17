"""Transport implementations for public web pages and JSON APIs."""

from __future__ import annotations

import json
import time
from typing import Any
from urllib.error import HTTPError, URLError
from urllib.request import Request, urlopen

from .browser import BrowserSession, BrowserSettings
from .errors import ScraperError


FILE_TYPES = frozenset({"application/pdf", "image/png", "image/jpeg", "image/webp"})


class PublicPageFetcher:
    """Fetch public HTML/JSON with a bounded request rate.

    HTML goes through plain HTTP by default, or through a Chrome session when
    ``browser`` is enabled (see ``scraper.browser``). JSON APIs always use HTTP.
    """

    user_agent = "StartupGoResearchBot/0.1 (+public research; contact repository owner)"

    def __init__(
        self,
        *,
        timeout: float = 20,
        delay: float = 1.0,
        browser: bool = False,
        browser_settings: BrowserSettings | None = None,
    ):
        self.timeout = timeout
        self.delay = max(0.0, delay)
        self.browser = browser
        self._last_request = 0.0
        self._session = BrowserSession(browser_settings or BrowserSettings(), timeout=timeout) if browser else None

    def fetch_text(self, url: str) -> str:
        self._wait_for_rate_limit()
        if self._session is not None:
            return self._session.render(url)
        response = self._request(url, "text/html,application/xhtml+xml")
        try:
            return response.read().decode(response.headers.get_content_charset() or "utf-8", "replace")
        finally:
            response.close()

    def fetch_json(self, url: str) -> Any:
        self._wait_for_rate_limit()
        response = self._request(url, "application/json")
        try:
            return json.loads(response.read().decode("utf-8"))
        except json.JSONDecodeError as exc:
            raise ScraperError(f"{url} returned invalid JSON") from exc
        finally:
            response.close()

    def fetch_file(self, url: str, *, max_bytes: int = 15_000_000) -> tuple[str, bytes]:
        """A PDF or image as (content type, bytes). Always plain HTTP: a browser displays these instead of handing them over.

        With a browser session the request carries the browser's user agent, like the pages it renders.
        """
        self._wait_for_rate_limit()
        user_agent = self._session.user_agent() if self._session is not None else None
        response = self._request(url, "application/pdf,image/*", FILE_TYPES, user_agent)
        try:
            data = response.read(max_bytes + 1)
            content_type = response.headers.get_content_type()
        finally:
            response.close()
        if len(data) > max_bytes:
            raise ScraperError(f"{url} is larger than {max_bytes // 1_000_000} MB")
        return content_type, data

    def close(self) -> None:
        if self._session is not None:
            self._session.close()

    def _request(
        self, url: str, accepted_content_type: str, accepted_types: frozenset[str] | None = None, user_agent: str | None = None
    ):
        request = Request(
            url,
            headers={"User-Agent": user_agent or self.user_agent, "Accept": accepted_content_type},
        )
        try:
            response = urlopen(request, timeout=self.timeout)
        except HTTPError as exc:
            if exc.code in {401, 403, 429}:
                raise ScraperError(
                    f"{url} denied automated access with HTTP {exc.code}. "
                    "Use a permitted public URL, an official API/data export, or "
                    "enable browser mode if the page is publicly accessible there; "
                    "do not bypass CAPTCHAs or access controls."
                ) from exc
            raise ScraperError(f"could not fetch {url}: {exc}") from exc
        except (URLError, TimeoutError) as exc:
            raise ScraperError(f"could not fetch {url}: {exc}") from exc
        content_type = response.headers.get_content_type()
        if accepted_types is not None:
            accepted = accepted_types
        elif accepted_content_type == "application/json":
            accepted = {"application/json", "application/geo+json"}
        else:
            accepted = {"text/html", "application/xhtml+xml"}
        if content_type not in accepted:
            response.close()
            raise ScraperError(f"{url} returned unsupported content type {content_type}")
        return response

    def _wait_for_rate_limit(self) -> None:
        elapsed = time.monotonic() - self._last_request
        if elapsed < self.delay:
            time.sleep(self.delay - elapsed)
        self._last_request = time.monotonic()
