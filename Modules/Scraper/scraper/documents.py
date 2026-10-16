"""Public document loading and readable-text extraction."""

from __future__ import annotations

from dataclasses import dataclass

from .fetchers import PublicPageFetcher


@dataclass(slots=True)
class SourceDocument:
    url: str
    title: str
    text: str
    source: str


class PublicDocumentService:
    """Turn public HTML pages into bounded documents for an AI provider."""

    def __init__(self, fetcher: PublicPageFetcher, max_characters: int = 12000):
        self.fetcher = fetcher
        self.max_characters = max_characters

    def load(self, *, url: str, source: str) -> SourceDocument:
        html = self.fetcher.fetch_text(url)
        from bs4 import BeautifulSoup

        document = BeautifulSoup(html, "html.parser")
        title = document.title.get_text(" ", strip=True) if document.title else ""
        for element in document(["script", "style", "noscript"]):
            element.decompose()
        text = document.get_text(" ", strip=True)
        return SourceDocument(
            url=url,
            title=title,
            text=text[: self.max_characters],
            source=source,
        )
