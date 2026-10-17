"""Unit tests for browser settings, challenge detection and fetcher wiring (no real browser)."""

from __future__ import annotations

import unittest
from typing import Any

from scraper.browser import BrowserSession, BrowserSettings, detect_challenge
from scraper.errors import ScraperError
from scraper.fetchers import PublicPageFetcher


class FakeDriver:
    def __init__(self, html: str):
        self.page_source = html
        self.visited: list[str] = []
        self.quit_called = False

    def set_page_load_timeout(self, _: float) -> None: ...

    def get(self, url: str) -> None:
        self.visited.append(url)

    def execute_script(self, _: str) -> Any:
        return "complete"

    def quit(self) -> None:
        self.quit_called = True


class FakeSession(BrowserSession):
    """BrowserSession with an injected driver instead of launching Chrome."""

    def __init__(self, html: str):
        super().__init__(BrowserSettings(stealth=False, settle_seconds=0), timeout=5)
        self.fake = FakeDriver(html)

    def _create_driver(self) -> Any:
        return self.fake


class UserAgentTest(unittest.TestCase):
    def session(self, cdp_result: Any, stealth: bool) -> FakeSession:
        session = FakeSession("")
        session.settings = BrowserSettings(stealth=stealth, settle_seconds=0)
        session.fake.execute_cdp_cmd = lambda command, params: cdp_result  # type: ignore[attr-defined]
        session.fake.execute_script = lambda script: "Mozilla/5.0 HeadlessChrome/155"  # type: ignore[method-assign]
        session._apply_stealth = lambda driver: None  # type: ignore[method-assign]
        return session

    def test_stealth_hides_headless_in_the_user_agent(self):
        session = self.session({"userAgent": "Mozilla/5.0 HeadlessChrome/155"}, stealth=True)
        self.assertEqual(session.user_agent(), "Mozilla/5.0 Chrome/155")
        self.assertEqual(self.session({"userAgent": "Mozilla/5.0 HeadlessChrome/155"}, stealth=False).user_agent(), "Mozilla/5.0 HeadlessChrome/155")

    def test_falls_back_to_the_page_when_the_browser_gives_no_version(self):
        self.assertEqual(self.session(None, stealth=True).user_agent(), "Mozilla/5.0 Chrome/155")


class BrowserSettingsTest(unittest.TestCase):
    def test_defaults_use_undetected_driver_with_stealth(self):
        s = BrowserSettings.from_mapping({})
        self.assertEqual((s.driver, s.stealth, s.headless, s.chrome_version), ("undetected", True, True, None))

    def test_parses_overrides(self):
        s = BrowserSettings.from_mapping(
            {"driver": "Selenium", "stealth": False, "chrome_version": 155, "window_size": [800, 600]}
        )
        self.assertEqual((s.driver, s.stealth, s.chrome_version, s.window_size), ("selenium", False, 155, (800, 600)))

    def test_rejects_unknown_driver(self):
        with self.assertRaises(ScraperError):
            BrowserSettings.from_mapping({"driver": "firefox"})


class DetectChallengeTest(unittest.TestCase):
    def test_flags_challenge_titles_and_vendor_markers(self):
        self.assertEqual(detect_challenge("<title>Just a moment...</title>"), "just a moment")
        self.assertEqual(detect_challenge("<title>Shop</title><script>window._cf_chl_opt={}</script>"), "_cf_chl_opt")
        self.assertEqual(detect_challenge('<div id="px-captcha"></div>'), "px-captcha")

    def test_ignores_normal_pages_that_mention_captcha(self):
        html = '<title>Sign in | Example</title><form><div class="g-recaptcha"></div></form><p>Access denied?</p>'
        self.assertIsNone(detect_challenge(html))


class BrowserSessionTest(unittest.TestCase):
    def test_render_returns_html_and_closes(self):
        session = FakeSession("<title>Startups</title><h1>Kelp Co</h1>")
        self.assertIn("Kelp Co", session.render("https://example.org"))
        session.close()
        self.assertTrue(session.fake.quit_called)

    def test_render_refuses_challenge_pages(self):
        session = FakeSession("<title>Attention Required! | Cloudflare</title>")
        with self.assertRaisesRegex(ScraperError, "Not attempting to bypass"):
            session.render("https://example.org")


class FetcherWiringTest(unittest.TestCase):
    def test_browser_mode_renders_html_through_the_session(self):
        fetcher = PublicPageFetcher(delay=0, browser=True)
        fetcher._session = FakeSession("<title>ok</title>")
        self.assertEqual(fetcher.fetch_text("https://example.org"), "<title>ok</title>")
        self.assertEqual(fetcher._session.fake.visited, ["https://example.org"])

    def test_http_mode_has_no_browser_session(self):
        self.assertIsNone(PublicPageFetcher(browser=False)._session)


if __name__ == "__main__":
    unittest.main()
