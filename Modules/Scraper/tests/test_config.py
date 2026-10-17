"""config.toml loading and command-line overrides."""

from __future__ import annotations

import tempfile
import unittest
from pathlib import Path

from scraper.cli import build_settings, parse_args
from scraper.config import AppSettings
from scraper.errors import ScraperError

CONFIG = """
[scraper]
timeout = 12.0
delay = 3.0
browser = true

[browser]
driver = "selenium"
stealth = false
"""


class ConfigTest(unittest.TestCase):
    def setUp(self):
        self.dir = tempfile.TemporaryDirectory()
        self.path = Path(self.dir.name) / "config.toml"
        self.path.write_text(CONFIG, encoding="utf-8")

    def tearDown(self):
        self.dir.cleanup()

    def test_loads_scraper_and_browser_tables(self):
        settings = AppSettings.load(self.path)
        self.assertEqual((settings.scraper.timeout, settings.scraper.delay, settings.scraper.browser), (12.0, 3.0, True))
        self.assertEqual((settings.browser.driver, settings.browser.stealth), ("selenium", False))

    def test_missing_file_is_an_error(self):
        with self.assertRaises(ScraperError):
            AppSettings.load(Path(self.dir.name) / "missing.toml")

    def test_config_values_apply_when_no_flags_are_given(self):
        settings = build_settings(parse_args(["--config", str(self.path)]))
        self.assertTrue(settings.scraper.browser)
        self.assertEqual(settings.scraper.delay, 3.0)
        self.assertTrue(settings.browser.headless)

    def test_flags_override_config(self):
        args = parse_args(
            ["--config", str(self.path), "--no-browser", "--delay", "0.5", "--driver", "undetected", "--stealth", "--headed"]
        )
        settings = build_settings(args)
        self.assertEqual((settings.scraper.browser, settings.scraper.delay, settings.scraper.timeout), (False, 0.5, 12.0))
        self.assertEqual((settings.browser.driver, settings.browser.stealth, settings.browser.headless), ("undetected", True, False))


if __name__ == "__main__":
    unittest.main()
