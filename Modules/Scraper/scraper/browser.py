"""Chrome browser sessions for rendering JavaScript-heavy public pages.

Two driver backends are supported:

* ``undetected`` (default): undetected-chromedriver, which patches the
  chromedriver binary so Chrome does not advertise itself as automated.
* ``selenium``: the stock Selenium Chrome driver.

Either backend can additionally apply selenium-stealth, which masks common
automation fingerprints (``navigator.webdriver``, WebGL vendor, languages, ...).

Sessions never try to defeat CAPTCHAs or access controls: if a page responds
with a challenge or block page, a ``ScraperError`` is raised instead.
"""

from __future__ import annotations

import re
import sys
import time
from dataclasses import dataclass, field
from typing import Any, Literal

from .errors import ScraperError

DriverKind = Literal["undetected", "selenium"]

# Generic phrases, matched against the page <title> only (body text gives false positives).
CHALLENGE_TITLE_MARKERS = (
    "just a moment",
    "attention required",
    "access denied",
    "verify you are human",
    "are you a robot",
    "security check",
    "captcha",
)
# Vendor markers that only appear on interstitial challenge pages, matched anywhere in the HTML.
CHALLENGE_PAGE_MARKERS = (
    "_cf_chl_opt",  # Cloudflare challenge
    "px-captcha",  # HUMAN / PerimeterX
    "captcha-delivery.com",  # DataDome
)
_TITLE_PATTERN = re.compile(r"<title[^>]*>(.*?)</title>", re.IGNORECASE | re.DOTALL)


@dataclass(frozen=True, slots=True)
class BrowserSettings:
    driver: DriverKind = "undetected"
    stealth: bool = True
    headless: bool = True
    # Major Chrome version for undetected-chromedriver; None lets it detect the installed one.
    chrome_version: int | None = None
    window_size: tuple[int, int] = (1440, 1200)
    languages: tuple[str, ...] = ("en-US", "en")
    # Extra seconds to let client-side rendering settle after the load event.
    settle_seconds: float = 2.0
    # Optional persistent Chrome profile directory (keeps cookies/consent between runs).
    user_data_dir: str = ""
    # Linux only: run a headed browser inside a virtual X display (xvfbwrapper).
    virtual_display: bool = False
    extra_arguments: tuple[str, ...] = field(default_factory=tuple)

    @classmethod
    def from_mapping(cls, data: dict[str, Any]) -> BrowserSettings:
        driver = str(data.get("driver", "undetected")).casefold()
        if driver not in ("undetected", "selenium"):
            raise ScraperError(f"[browser] driver must be 'undetected' or 'selenium', not {driver!r}")
        width, height = data.get("window_size", (1440, 1200))
        version = int(data.get("chrome_version", 0) or 0)
        return cls(
            driver=driver,  # type: ignore[arg-type]
            stealth=bool(data.get("stealth", True)),
            headless=bool(data.get("headless", True)),
            chrome_version=version or None,
            window_size=(int(width), int(height)),
            languages=tuple(data.get("languages", ("en-US", "en"))),
            settle_seconds=max(0.0, float(data.get("settle_seconds", 2.0))),
            user_data_dir=str(data.get("user_data_dir", "")),
            virtual_display=bool(data.get("virtual_display", False)),
            extra_arguments=tuple(data.get("extra_arguments", ())),
        )


def detect_challenge(html: str) -> str | None:
    """Return the matching marker if the page looks like a bot challenge or block page."""
    match = _TITLE_PATTERN.search(html)
    title = match.group(1).casefold() if match else ""
    page = html.casefold()
    return next((m for m in CHALLENGE_TITLE_MARKERS if m in title), None) or next(
        (m for m in CHALLENGE_PAGE_MARKERS if m in page), None
    )


def stealth_platform() -> str:
    """navigator.platform value consistent with the real OS, so fingerprints don't contradict."""
    if sys.platform == "darwin":
        return "MacIntel"
    if sys.platform.startswith("win"):
        return "Win32"
    return "Linux x86_64"


class BrowserSession:
    """Lazily started Chrome session; call ``close()`` when done."""

    def __init__(self, settings: BrowserSettings, *, timeout: float):
        self.settings = settings
        self.timeout = timeout
        self._driver: Any = None
        self._display: Any = None

    def render(self, url: str) -> str:
        driver = self._ensure_driver()
        try:
            driver.get(url)
            self._wait_until_loaded(driver)
            html = driver.page_source
        except ScraperError:
            raise
        except Exception as exc:  # selenium raises many WebDriverException subclasses
            raise ScraperError(f"browser could not load {url}: {exc}") from exc

        if marker := detect_challenge(html):
            raise ScraperError(
                f"{url} served a bot challenge or block page ({marker!r}). "
                "Not attempting to bypass it; use an official API, a data export, "
                "or a source that permits automated access."
            )
        return html

    def close(self) -> None:
        if self._driver is not None:
            try:
                self._driver.quit()
            finally:
                self._driver = None
        if self._display is not None:
            self._display.stop()
            self._display = None

    # ------------------------------------------------------------------ setup

    def _ensure_driver(self) -> Any:
        if self._driver is None:
            self._start_virtual_display()
            self._driver = self._create_driver()
            self._driver.set_page_load_timeout(self.timeout)
            if self.settings.stealth:
                self._apply_stealth(self._driver)
        return self._driver

    def _chrome_arguments(self) -> list[str]:
        width, height = self.settings.window_size
        return [
            f"--window-size={width},{height}",
            f"--lang={self.settings.languages[0]}",
            "--no-first-run",
            "--no-default-browser-check",
            *self.settings.extra_arguments,
        ]

    def _create_driver(self) -> Any:
        if self.settings.driver == "undetected":
            return self._create_undetected_driver()
        return self._create_selenium_driver()

    def _create_undetected_driver(self) -> Any:
        try:
            import undetected_chromedriver as uc
        except ImportError as exc:
            raise ScraperError(
                "driver 'undetected' requires the undetected-chromedriver package "
                "(note: version 3.5.x needs Python < 3.12)"
            ) from exc

        options = uc.ChromeOptions()
        for argument in self._chrome_arguments():
            options.add_argument(argument)
        try:
            return uc.Chrome(
                options=options,
                headless=self.settings.headless,
                version_main=self.settings.chrome_version,
                user_data_dir=self.settings.user_data_dir or None,
            )
        except Exception as exc:
            raise ScraperError(
                f"could not start undetected Chrome: {exc}. If the Chrome and driver versions "
                "differ, set [browser] chrome_version to your Chrome major version."
            ) from exc

    def _create_selenium_driver(self) -> Any:
        try:
            from selenium import webdriver
        except ImportError as exc:
            raise ScraperError("driver 'selenium' requires the selenium package") from exc

        options = webdriver.ChromeOptions()
        for argument in self._chrome_arguments():
            options.add_argument(argument)
        if self.settings.headless:
            options.add_argument("--headless=new")
        if self.settings.user_data_dir:
            options.add_argument(f"--user-data-dir={self.settings.user_data_dir}")
        if self.settings.stealth:
            # The stock driver advertises automation through these switches.
            options.add_experimental_option("excludeSwitches", ["enable-automation"])
            options.add_experimental_option("useAutomationExtension", False)
            options.add_argument("--disable-blink-features=AutomationControlled")
        try:
            return webdriver.Chrome(options=options)
        except Exception as exc:
            raise ScraperError(f"could not start Chrome: {exc}") from exc

    def _apply_stealth(self, driver: Any) -> None:
        try:
            from selenium_stealth import stealth
        except ImportError as exc:
            raise ScraperError("stealth mode requires the selenium-stealth package") from exc

        # Headless Chrome reports "HeadlessChrome" in its user agent; present the regular one.
        user_agent = driver.execute_cdp_cmd("Browser.getVersion", {})["userAgent"].replace("HeadlessChrome", "Chrome")
        stealth(
            driver,
            user_agent=user_agent,
            languages=list(self.settings.languages),
            vendor="Google Inc.",
            platform=stealth_platform(),
            webgl_vendor="Intel Inc.",
            renderer="Intel Iris OpenGL Engine",
            fix_hairline=True,
        )

    def _start_virtual_display(self) -> None:
        if not self.settings.virtual_display or self.settings.headless or not sys.platform.startswith("linux"):
            return
        try:
            from xvfbwrapper import Xvfb
        except ImportError as exc:
            raise ScraperError("virtual_display requires the xvfbwrapper package and Xvfb") from exc
        width, height = self.settings.window_size
        self._display = Xvfb(width=width, height=height)
        self._display.start()

    # ---------------------------------------------------------------- loading

    def _wait_until_loaded(self, driver: Any) -> None:
        deadline = time.monotonic() + self.timeout
        while driver.execute_script("return document.readyState") != "complete":
            if time.monotonic() > deadline:
                raise ScraperError(f"page did not finish loading within {self.timeout:.0f}s")
            time.sleep(0.25)
        if self.settings.settle_seconds:
            time.sleep(self.settings.settle_seconds)
