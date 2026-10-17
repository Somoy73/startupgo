from startup_agent.documents import (
    RobotsPolicy,
    SourceDocument,
    classify_source,
    documents_for_section,
    html_to_document,
    locate_quote,
    quote_in_text,
    rank_links,
    section_tags,
)


def doc(url: str, text: str = "x", *, source_type: str = "website", home: bool = False) -> SourceDocument:
    return SourceDocument(url, "", text, source_type, "2026-10-17", home)


class TestQuotes:
    def test_exact_match_ignores_case_whitespace_and_typographic_quotes(self):
        text = "In 2025 we completed a paid  pilot with Port of Turku’s harbour."
        assert quote_in_text('in 2025 we completed a paid pilot with Port of Turku\'s', text) == (True, True)

    def test_ellipsis_fragments_must_appear_in_order(self):
        text = "Our buoys measure waves in real time. Data is sold to ports as a subscription."
        assert quote_in_text("Our buoys measure waves ... sold to ports as a subscription", text) == (True, False)
        assert quote_in_text("sold to ports as a subscription ... Our buoys measure waves", text) == (False, False)

    def test_paraphrase_is_not_found(self):
        assert quote_in_text("We ran a paid pilot in Turku", "In 2025 we completed a paid pilot with Port of Turku.") == (False, False)

    def test_locate_prefers_cited_document_then_searches_others(self):
        a, b = doc("https://a", "alpha beta gamma"), doc("https://b", "delta epsilon zeta")
        assert locate_quote("delta epsilon", [a, b], "https://a") == (b, True)
        assert locate_quote("missing words here", [a, b], None) == (None, False)


class TestHtml:
    def test_strips_scripts_and_collects_links(self):
        html = '<title>Acme | Team</title><script>var x=1</script><p>Hello <b>world</b></p><a href="/about#x">About</a>'
        document, links = html_to_document("https://acme.fi/", html, source_type="website", retrieved_at="d", max_chars=100)
        assert document.title == "Acme | Team"
        assert document.text == "Acme | Team Hello world About"
        assert links == ["https://acme.fi/about"]


class TestRouting:
    def test_section_tags_from_url_and_title(self):
        assert {"F"} <= section_tags("https://acme.fi/our-team")
        assert "E" in section_tags("https://acme.fi/x", "Sustainability report")

    def test_rank_links_keeps_relevant_same_site_pages(self):
        links = [
            "https://acme.fi/technology",
            "https://www.acme.fi/about/team",
            "https://other.com/news",
            "https://acme.fi/brochure.pdf",
            "mailto:hi@acme.fi",
            "https://acme.fi/xyz",
            "https://acme.fi/sign-up-to-our-newsletter",
            "https://acme.fi/news/privacy-policy",
        ]
        # Pages relevant to more sections come first ("about/team" feeds A, B, F, G, H).
        assert rank_links(links, "acme.fi", exclude=set()) == ["https://www.acme.fi/about/team", "https://acme.fi/technology"]

    def test_documents_for_section_prioritises_and_respects_budget(self):
        team = doc("https://acme.fi/team", "t" * 50)
        home = doc("https://acme.fi/", "h" * 50, home=True)
        news = doc("https://news.com/acme", "n" * 50, source_type="news")
        other = doc("https://acme.fi/xyz", "o" * 50)
        chosen = documents_for_section("F", [other, news, home, team], max_chars=120)
        assert [d.url for d in chosen] == ["https://acme.fi/team", "https://acme.fi/", "https://news.com/acme"]
        assert sum(len(d.text) for d in chosen) == 120

    def test_classify_source(self):
        assert classify_source("https://www.acme.fi/x", "acme.fi") == "website"
        assert classify_source("https://cordis.europa.eu/project/id/1", "acme.fi") == "eu_projects"
        assert classify_source("https://yle.fi/news", "acme.fi") == "news"


class TestRobots:
    def test_disallow_and_unreadable(self):
        bodies = {"https://a.fi/robots.txt": "User-agent: *\nDisallow: /private", "https://b.fi/robots.txt": None}
        policy = RobotsPolicy(bodies.get, "Bot")
        assert policy.allowed("https://a.fi/team")
        assert not policy.allowed("https://a.fi/private/x")
        assert policy.allowed("https://b.fi/anything")
