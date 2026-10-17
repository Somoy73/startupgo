"""Source documents: HTML to text, same-site crawling, robots.txt, and routing pages to sections."""

from __future__ import annotations

import re
from collections.abc import Callable, Iterable
from dataclasses import dataclass
from urllib.parse import urldefrag, urljoin, urlsplit
from urllib.robotparser import RobotFileParser

from bs4 import BeautifulSoup, Tag

from .spec import SECTIONS
from .vocab import SourceType

_SKIP_EXTENSIONS = re.compile(r"\.(pdf|jpe?g|png|gif|svg|webp|zip|mp4|mov|docx?|pptx?|xlsx?|csv|xml|json)$", re.IGNORECASE)
_STRIP_TAGS = ["script", "style", "noscript", "svg", "template", "iframe"]
# Pages with no facts worth an LLM call.
_CONSENT_ELEMENT = re.compile(r"cookie|consent|gdpr", re.IGNORECASE)
_SKIP_PATHS = re.compile(r"newsletter|subscribe|sign-?up|sign-?in|log-?in|register|cart|checkout|cookie|privacy|terms|gdpr", re.IGNORECASE)

# Domains whose pages count as independent sources of a given type.
_SOURCE_TYPE_BY_DOMAIN: tuple[tuple[str, SourceType], ...] = (
    ("cordis.europa.eu", "eu_projects"),
    ("avoindata.prh.fi", "registry"),
    ("ytj.fi", "registry"),
    ("businessfinland.fi", "grant_db"),
    ("patents.google.com", "patent"),
    ("espacenet.com", "patent"),
    ("epo.org", "patent"),
)


@dataclass(frozen=True, slots=True)
class SourceDocument:
    url: str
    title: str
    text: str
    source_type: SourceType
    retrieved_at: str
    is_homepage: bool = False


def host(url: str) -> str:
    return (urlsplit(url).hostname or "").removeprefix("www.")


def same_site(url: str, site_host: str) -> bool:
    h = host(url)
    return h == site_host or h.endswith("." + site_host)


def classify_source(url: str, site_host: str) -> SourceType:
    """website for the startup's own pages, a typed source for known registries, news otherwise."""
    if same_site(url, site_host):
        return "website"
    h = host(url)
    return next((t for domain, t in _SOURCE_TYPE_BY_DOMAIN if h == domain or h.endswith("." + domain)), "news")


def html_to_document(
    url: str,
    html: str,
    *,
    source_type: SourceType,
    retrieved_at: str,
    max_chars: int,
    is_homepage: bool = False,
    readable: bool = False,
) -> tuple[SourceDocument, list[str]]:
    """Readable text plus the outgoing links of a page.

    ``readable`` keeps only the page's main content when it has one, else everything except cookie-consent
    dialogs: those come first in the markup and can fill ``max_chars`` before the content starts. Off by
    default because navigation and footers carry facts the startup research quotes (addresses, company names).
    """
    soup = BeautifulSoup(html, "html.parser")
    title = " ".join(soup.title.get_text(" ", strip=True).split()) if soup.title else ""
    links = [urldefrag(urljoin(url, a["href"]))[0] for a in soup.select("a[href]")]
    for tag in soup(_STRIP_TAGS):
        tag.decompose()
    root = (_main_content(soup) or _without_consent(soup)) if readable else soup
    text = " ".join(root.get_text(" ", strip=True).split())[:max_chars]
    return SourceDocument(url, title, text, source_type, retrieved_at, is_homepage), links


def _main_content(soup: BeautifulSoup) -> Tag | None:
    main = soup.find("main") or soup.find(attrs={"role": "main"})
    return main if isinstance(main, Tag) and len(main.get_text(strip=True)) >= 200 else None


def _without_consent(soup: BeautifulSoup) -> BeautifulSoup:
    """The page without cookie-consent dialogs (elements named cookie/consent/gdpr that aren't most of the page)."""
    total = len(soup.get_text(strip=True))
    for tag in soup.find_all(True):
        if tag.decomposed or tag.name in ("html", "body"):
            continue
        name = f"{tag.get('id') or ''} {' '.join(tag.get('class') or [])}"
        if _CONSENT_ELEMENT.search(name) and len(tag.get_text(strip=True)) < total * 0.6:
            tag.decompose()
    return soup


def section_tags(url: str, title: str = "") -> set[str]:
    """Sections whose keywords appear in the page's URL path or title."""
    haystack = f"{urlsplit(url).path} {title}".lower()
    return {sid for sid, s in SECTIONS.items() if any(k in haystack for k in s.keywords)}


def rank_links(links: Iterable[str], site_host: str, *, exclude: set[str]) -> list[str]:
    """Same-site HTML links, most section-relevant and shallowest first."""
    candidates: dict[str, tuple[int, int]] = {}
    for link in links:
        parts = urlsplit(link)
        if parts.scheme not in ("http", "https") or not same_site(link, site_host):
            continue
        if _SKIP_EXTENSIONS.search(parts.path) or _SKIP_PATHS.search(parts.path):
            continue
        clean = f"{parts.scheme}://{parts.netloc}{parts.path.rstrip('/') or '/'}"
        if clean in exclude or clean in candidates:
            continue
        tags = section_tags(clean)
        if not tags:
            continue
        candidates[clean] = (-len(tags), parts.path.count("/"))
    return sorted(candidates, key=candidates.__getitem__)


def documents_for_section(section_id: str, documents: list[SourceDocument], max_chars: int) -> list[SourceDocument]:
    return documents_for_sections([section_id], documents, max_chars)


def documents_for_sections(section_ids: Iterable[str], documents: list[SourceDocument], max_chars: int) -> list[SourceDocument]:
    """Pick the documents relevant to the given sections, within a character budget.

    Order: pages routed to any of the sections, then the homepage, then independent sources
    (news, registries), then any remaining pages.
    """
    wanted = set(section_ids)

    def priority(doc: SourceDocument) -> int:
        if wanted & section_tags(doc.url, doc.title):
            return 0
        if doc.is_homepage:
            return 1
        if doc.source_type != "website":
            return 2
        return 3

    chosen: list[SourceDocument] = []
    budget = max_chars
    for doc in sorted(documents, key=priority):
        if budget <= 0:
            break
        if priority(doc) == 3 and chosen:
            continue  # unrelated website pages only when nothing else is available
        text = doc.text[:budget]
        chosen.append(doc if text == doc.text else SourceDocument(doc.url, doc.title, text, doc.source_type, doc.retrieved_at, doc.is_homepage))
        budget -= len(text)
    return chosen


class RobotsPolicy:
    """Per-host robots.txt check. Unreadable robots.txt means allowed."""

    def __init__(self, fetch_robots: Callable[[str], str | None], user_agent: str):
        self._fetch = fetch_robots
        self._user_agent = user_agent
        self._parsers: dict[str, RobotFileParser | None] = {}

    def allowed(self, url: str) -> bool:
        parts = urlsplit(url)
        origin = f"{parts.scheme}://{parts.netloc}"
        if origin not in self._parsers:
            body = self._fetch(f"{origin}/robots.txt")
            parser = None
            if body is not None:
                parser = RobotFileParser()
                parser.parse(body.splitlines())
            self._parsers[origin] = parser
        parser = self._parsers[origin]
        return parser is None or parser.can_fetch(self._user_agent, url)


# --- Quote verification --------------------------------------------------------------

_QUOTE_CHARS = str.maketrans({"‘": "'", "’": "'", "“": '"', "”": '"', "–": "-", "—": "-", " ": " "})
_ELLIPSIS = re.compile(r"\s*(?:\.\.\.|…)\s*")


def normalize(text: str) -> str:
    return " ".join(text.translate(_QUOTE_CHARS).lower().split())


def quote_in_text(quote: str, text: str) -> tuple[bool, bool]:
    """(found, exact). A quote with "..." matches if its fragments appear in order."""
    haystack = normalize(text)
    needle = normalize(quote).strip(" \"'")
    if not needle:
        return False, False
    if needle in haystack:
        return True, True
    fragments = [f.strip(" \"'") for f in _ELLIPSIS.split(needle) if len(f.split()) >= 3]
    if len(fragments) < 2:
        return False, False
    position = 0
    for fragment in fragments:
        position = haystack.find(fragment, position)
        if position < 0:
            return False, False
        position += len(fragment)
    return True, False


def locate_quote(quote: str, documents: list[SourceDocument], preferred_url: str | None) -> tuple[SourceDocument | None, bool]:
    """Find the document containing the quote, trying the cited URL first."""
    ordered = sorted(documents, key=lambda d: d.url != preferred_url)
    for doc in ordered:
        found, exact = quote_in_text(quote, doc.text)
        if found:
            return doc, exact
    return None, False
