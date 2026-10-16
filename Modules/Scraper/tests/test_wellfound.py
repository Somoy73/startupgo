"""Wellfound collection-page parsing against a synthetic __NEXT_DATA__ payload."""

from __future__ import annotations

import json
import unittest

from scraper.errors import ScraperError
from scraper.wellfound import WellfoundAdapter


def collection_page(startups: list[dict], *, page_count: int = 1) -> str:
    apollo = {
        "ROOT_QUERY": {
            "talent": {
                'seoLandingPageStartupSearchResults({"market":"oceans","page":1})': {
                    "totalStartupCount": len(startups),
                    "pageCount": page_count,
                    "startups": [{"__ref": f"StartupResult:{s['id']}"} for s in startups],
                }
            }
        },
        "NewTag:1": {"displayName": "Finland"},
        "NewTag:2": {"displayName": "Clean Technology"},
        "Badge:STAGE": {"name": "COMPANY_STAGE_BADGE", "label": "Early Stage"},
        "Badge:B2B": {"name": "B2B_BADGE", "label": "B2B"},
    }
    for s in startups:
        apollo[f"StartupResult:{s['id']}"] = {
            "id": s["id"],
            "name": s["name"],
            "slug": s["name"].lower(),
            "highConcept": "Kelp  farming robots",
            "description": "We build robots.",
            "companyUrl": f"https://{s['name'].lower()}.fi",
            "locationTaggings": [{"__ref": "NewTag:1"}],
            "marketTaggings": [{"__ref": "NewTag:2"}],
            "badges": [{"__ref": "Badge:B2B"}, {"__ref": "Badge:STAGE"}],
        }
    payload = {"props": {"pageProps": {"apolloState": {"data": apollo}}}}
    return f'<html><script id="__NEXT_DATA__" type="application/json">{json.dumps(payload)}</script></html>'


class FakeFetcher:
    def __init__(self, pages: dict[str, str]):
        self.pages = pages
        self.requested: list[str] = []

    def fetch_text(self, url: str) -> str:
        self.requested.append(url)
        return self.pages[url]

    def fetch_json(self, url: str):  # pragma: no cover - unused
        raise NotImplementedError


BASE = "https://wellfound.com/startups/industry/oceans"


class WellfoundAdapterTest(unittest.TestCase):
    def test_parses_leads_from_next_data(self):
        page = WellfoundAdapter().parse(collection_page([{"id": "1", "name": "Aqua"}]), BASE)
        lead = page.leads[0]
        self.assertEqual(
            (lead.name, lead.website, lead.tagline, lead.location, lead.sector, lead.stage, lead.external_id),
            ("Aqua", "https://aqua.fi", "Kelp farming robots", "Finland", "Clean Technology", "Early Stage", "aqua"),
        )
        self.assertEqual(lead.source_url, BASE)

    def test_follows_pages_until_limit(self):
        fetcher = FakeFetcher(
            {
                BASE: collection_page([{"id": "1", "name": "A"}, {"id": "2", "name": "B"}], page_count=3),
                f"{BASE}?page=2": collection_page([{"id": "3", "name": "C"}, {"id": "4", "name": "D"}], page_count=3),
            }
        )
        leads = WellfoundAdapter().collect(url=BASE + "/", fetcher=fetcher, limit=3)
        self.assertEqual([lead.name for lead in leads], ["A", "B", "C"])
        self.assertEqual(fetcher.requested, [BASE, f"{BASE}?page=2"])

    def test_rejects_search_and_company_urls(self):
        for url in ("https://wellfound.com/search?q=ocean", "https://wellfound.com/company/aqua", "http://wellfound.com/startups/x"):
            with self.assertRaises(ScraperError):
                WellfoundAdapter().collect(url=url, fetcher=FakeFetcher({}), limit=1)

    def test_unknown_collection_redirect_is_an_error(self):
        generic = collection_page([{"id": "1", "name": "Unrelated"}])
        with self.assertRaisesRegex(ScraperError, "no collection"):
            WellfoundAdapter().parse(generic, "https://wellfound.com/startups/industry/marine-technology")

    def test_missing_payload_is_an_error(self):
        with self.assertRaises(ScraperError):
            WellfoundAdapter().parse("<html></html>", BASE)


if __name__ == "__main__":
    unittest.main()
