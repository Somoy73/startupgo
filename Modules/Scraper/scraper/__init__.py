"""StartupGo scraper: public page fetching and startup lead discovery.

Turning leads into evidence-backed, scored entries is the job of the separate
agent module (Modules/Agent); this package contains no AI.
"""

from .browser import BrowserSettings
from .config import AppSettings, ScraperSettings
from .errors import ScraperError
from .factory import create_fetcher
from .fetchers import PublicPageFetcher
from .models import StartupLead
from .service import StartupScraper

__all__ = [
    "AppSettings",
    "BrowserSettings",
    "PublicPageFetcher",
    "ScraperError",
    "ScraperSettings",
    "StartupLead",
    "StartupScraper",
    "create_fetcher",
]
