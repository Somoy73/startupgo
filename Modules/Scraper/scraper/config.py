"""Scraper settings from config.toml: request pacing and the optional Chrome browser."""

from __future__ import annotations

import tomllib
from dataclasses import dataclass, field
from pathlib import Path

from .browser import BrowserSettings
from .errors import ScraperError

# config.toml next to the package, used when no explicit path is given.
DEFAULT_CONFIG = Path(__file__).resolve().parents[1] / "config.toml"


@dataclass(frozen=True, slots=True)
class ScraperSettings:
    timeout: float = 30.0
    delay: float = 1.5  # minimum seconds between requests
    browser: bool = False  # render pages with Chrome; options in BrowserSettings


@dataclass(frozen=True, slots=True)
class AppSettings:
    scraper: ScraperSettings = field(default_factory=ScraperSettings)
    browser: BrowserSettings = field(default_factory=BrowserSettings)

    @classmethod
    def load(cls, path: Path | None = None) -> AppSettings:
        """Read ``path``, or the default config.toml if it exists, else built-in defaults."""
        if path is None:
            if not DEFAULT_CONFIG.exists():
                return cls()
            path = DEFAULT_CONFIG
        try:
            data = tomllib.loads(path.read_text(encoding="utf-8"))
        except (OSError, tomllib.TOMLDecodeError) as exc:
            raise ScraperError(f"could not read configuration {path}: {exc}") from exc

        scraper = data.get("scraper", {})
        defaults = ScraperSettings()
        return cls(
            scraper=ScraperSettings(
                timeout=float(scraper.get("timeout", defaults.timeout)),
                delay=float(scraper.get("delay", defaults.delay)),
                browser=bool(scraper.get("browser", defaults.browser)),
            ),
            browser=BrowserSettings.from_mapping(data.get("browser", {})),
        )
