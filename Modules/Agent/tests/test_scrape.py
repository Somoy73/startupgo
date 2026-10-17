"""The scrape agent: pages, PDFs, images and the web search in; quote-checked records, sources and gaps out."""

from types import SimpleNamespace

import pytest
from scraper.errors import ScraperError

from startup_agent.cache import JsonCache
from startup_agent.config import AgentSettings
from startup_agent.crawler import PageLoader
from startup_agent.documents import SourceDocument
from startup_agent.errors import AgentError
from startup_agent.llm import QuotaExhausted, UsageStats
from startup_agent.scrape import ScrapeAgent, ScrapeTask, _Run, batches, file_type, goal_links, pdf_text
from startup_agent.search import SearchHit

PAGES = {
    "https://funds.example/calls": "<title>Calls</title><p>Blue Call 2026 closes on 30 March 2026 and has a budget of EUR 12 million.</p>"
                                   '<a href="/files/ocean-guide.pdf">Guide</a><a href="/about">About</a><a href="/calls/blue-call-2026">Call</a>',
    "https://funds.example/calls/blue-call-2026": "<title>Blue Call</title><p>Applicants must be SMEs registered in the EU or Norway.</p>",
    "https://funds.example/about": "<title>About</title><p>The fund was founded in 2019 by the ministry.</p>",
    "https://walled.example/": "<title>Sign in</title><p>Sign in</p>",
}
EXTRACTION = {
    "summary": "One open call.",
    "records": [
        {"kind": "funding_call", "title": "Blue Call 2026", "details": "Open call, EUR 12 million.", "website": "", "attributes": [{"name": "deadline", "value": "30 March 2026"}, {"name": "empty", "value": ""},
                                                                                {"name": "source_url", "value": "https://funds.example/calls"}],
         "source_url": "https://wrong.example/", "quote": "closes on 30 March 2026 and has a budget of EUR 12 million"},
        {"kind": "funding_call", "title": "Invented Call", "details": "Not on the page.", "website": "", "attributes": [], "source_url": "https://funds.example/calls",
         "quote": "Invented Call opens in May"},
    ],
    "gaps": ["The eligibility rules are not on the listing page."],
}
REPORT_URL = "https://funds.example/report.pdf"
REPORT_TEXT = "Annual report 2025. Net revenue was EUR 4.2 million and the team grew to 31 people."
REPORT_EXTRACTION = {"summary": "A report.", "gaps": [], "records": [
    {"kind": "figure", "title": "Revenue 2025", "details": "", "website": "", "attributes": [], "source_url": REPORT_URL, "quote": "Net revenue was EUR 4.2 million"}]}
NVIDIA = '[llm]\nprovider = "openai-compatible"\nmultimodal = %s\n'


class FakeLLM:
    model = "fake"

    def __init__(self, response=EXTRACTION, transcript=REPORT_TEXT):
        self.response, self.transcript, self.calls, self.files = response, transcript, [], []

    def complete_json(self, *, system, user, schema):
        self.calls.append(user)
        return self.response

    def transcribe(self, prompt, *, data, mime):
        self.files.append((mime, len(data)))
        return self.transcript


class FakeFetcher:
    def __init__(self, files=None):
        self.files = files or {}

    def fetch_text(self, url):
        if url not in PAGES:
            raise ScraperError(f"404 {url}")
        return PAGES[url]

    def fetch_file(self, url):
        if url not in self.files:
            raise ScraperError(f"404 {url}")
        return self.files[url]


class FakeSearch:
    name = "fake"

    def __init__(self, urls):
        self.urls, self.queries = urls, []

    def search(self, query, *, limit):
        self.queries.append(query)
        return [SearchHit(u, "") for u in self.urls][:limit]


def minimal_pdf(text: str) -> bytes:
    """A one-page PDF with a correct cross-reference table; an empty text makes a page without a text layer."""
    content = f"BT /F1 12 Tf 72 712 Td ({text}) Tj ET" if text else ""
    objects = [
        "<< /Type /Catalog /Pages 2 0 R >>",
        "<< /Type /Pages /Kids [3 0 R] /Count 1 >>",
        "<< /Type /Page /Parent 2 0 R /MediaBox [0 0 612 792] /Contents 4 0 R /Resources << /Font << /F1 5 0 R >> >> >>",
        f"<< /Length {len(content)} >>\nstream\n{content}\nendstream",
        "<< /Type /Font /Subtype /Type1 /BaseFont /Helvetica >>",
    ]
    out, offsets = "%PDF-1.4\n", []
    for i, obj in enumerate(objects, 1):
        offsets.append(len(out))
        out += f"{i} 0 obj\n{obj}\nendobj\n"
    xref = len(out)
    out += f"xref\n0 {len(objects) + 1}\n0000000000 65535 f \n" + "".join(f"{o:010d} 00000 n \n" for o in offsets)
    out += f"trailer\n<< /Size {len(objects) + 1} /Root 1 0 R >>\nstartxref\n{xref}\n%%EOF\n"
    return out.encode("latin-1")


def make_run(tmp_path, task, *, llm=None, searcher=None, fetcher=None, progress=None, llm_toml=NVIDIA % "false"):
    config = tmp_path / "config.toml"
    config.write_text(f'{llm_toml}[paths]\ncache_dir = "{tmp_path / "cache"}"\n', encoding="utf-8")
    fetcher = fetcher or FakeFetcher()
    agent = SimpleNamespace(
        loader=PageLoader(fetcher.fetch_text, cache=JsonCache(tmp_path / "pages"), robots=None, today="2026-10-17", page_chars=5000),
        extractor=SimpleNamespace(llm=llm or FakeLLM()),
        searcher=searcher,
        usage=UsageStats(),
    )
    return _Run(agent, fetcher, AgentSettings.load(config), task, progress or (lambda message: None))


def test_records_carry_a_checked_quote_and_the_page_it_was_found_on(tmp_path):
    result = make_run(tmp_path, ScrapeTask("open blue calls", ("https://funds.example/calls",))).execute()

    found, invented = result["records"]
    assert found["evidence"] == "page" and found["source_url"] == "https://funds.example/calls"  # the cited URL was wrong
    assert found["attributes"] == [{"name": "deadline", "value": "30 March 2026"}]  # blank values and record fields dropped
    assert invented["evidence"] == "unverified"
    assert result["gaps"] == ["The eligibility rules are not on the listing page."]
    assert result["sources"] == [{"url": "https://funds.example/calls", "kind": "page", "status": "read", "detail": "Calls"}]


def test_unreadable_and_empty_pages_are_reported_as_sources_and_gaps(tmp_path):
    urls = ("https://funds.example/calls", "https://funds.example/missing", "https://walled.example/")
    result = make_run(tmp_path, ScrapeTask("open blue calls", urls)).execute()

    assert [s["status"] for s in result["sources"]] == ["read", "error", "empty"]
    assert any(g.startswith("Nothing from https://funds.example/missing") for g in result["gaps"])
    assert any(g.startswith("Nothing from https://walled.example/") for g in result["gaps"])
    assert len(result["records"]) == 2  # the readable page still gave records


def test_no_readable_page_is_a_gap_and_no_llm_call(tmp_path):
    llm = FakeLLM()
    result = make_run(tmp_path, ScrapeTask("calls", ("https://funds.example/missing",)), llm=llm).execute()

    assert result["records"] == [] and llm.calls == []
    assert result["gaps"][0] == "No page could be read, so there was nothing to extract."


def test_without_urls_the_goal_is_searched_and_login_walled_hits_are_skipped(tmp_path):
    searcher = FakeSearch(["https://www.linkedin.com/company/acme", "https://funds.example/about"])
    result = make_run(tmp_path, ScrapeTask("fund history"), searcher=searcher).execute()

    assert searcher.queries == ["fund history"]
    assert [s["url"] for s in result["sources"]] == ["https://funds.example/about"]


def test_an_exhausted_search_quota_is_reported_as_a_short_error(tmp_path):
    class Exhausted(FakeSearch):
        def search(self, query, *, limit):
            raise QuotaExhausted("Gemini search quota exhausted: 429 " + "x" * 500)

    with pytest.raises(AgentError, match="web search is unavailable") as error:
        make_run(tmp_path, ScrapeTask("fund news"), searcher=Exhausted([])).execute()
    assert len(str(error.value)) < 300


def test_without_urls_and_without_search_the_agent_asks_for_a_url(tmp_path):
    with pytest.raises(AgentError, match="give at least one URL"):
        make_run(tmp_path, ScrapeTask("fund history")).execute()
    with pytest.raises(AgentError, match="no readable pages"):
        make_run(tmp_path, ScrapeTask("x"), searcher=FakeSearch(["https://www.linkedin.com/in/x"])).execute()


def test_follow_links_reads_only_links_that_match_the_goal_within_max_pages(tmp_path):
    task = ScrapeTask("blue call eligibility", ("https://funds.example/calls",), follow_links=True)
    result = make_run(tmp_path, task).execute()
    assert [s["url"] for s in result["sources"]] == ["https://funds.example/calls", "https://funds.example/calls/blue-call-2026"]

    limited = make_run(tmp_path, ScrapeTask(task.goal, task.urls, follow_links=True, max_pages=1)).execute()
    assert [s["url"] for s in limited["sources"]] == ["https://funds.example/calls"]


def test_a_pdf_with_a_text_layer_is_read_without_the_model(tmp_path):
    llm = FakeLLM(REPORT_EXTRACTION)
    fetcher = FakeFetcher({REPORT_URL: ("application/pdf", minimal_pdf(REPORT_TEXT))})
    result = make_run(tmp_path, ScrapeTask("revenue", (REPORT_URL,)), llm=llm, fetcher=fetcher).execute()  # model reads no files

    assert result["sources"] == [{"url": REPORT_URL, "kind": "pdf", "status": "read", "detail": "report.pdf"}]
    assert [r["evidence"] for r in result["records"]] == ["page"]  # the quote is in the PDF's own text
    assert llm.files == [] and len(llm.calls) == 1


def test_an_image_is_transcribed_by_a_multimodal_model_and_marked_as_transcript(tmp_path):
    url = "https://funds.example/report-page-3.png"
    llm = FakeLLM({**REPORT_EXTRACTION, "records": [{**REPORT_EXTRACTION["records"][0], "source_url": url}]})
    fetcher = FakeFetcher({url: ("image/png", b"\x89PNG fake")})
    result = make_run(tmp_path, ScrapeTask("revenue", (url,)), llm=llm, fetcher=fetcher, llm_toml=NVIDIA % "true").execute()

    assert result["sources"] == [{"url": url, "kind": "image", "status": "read", "detail": "report-page-3.png"}]
    assert [r["evidence"] for r in result["records"]] == ["transcript"]
    assert llm.files == [("image/png", 9)]


def test_images_and_scanned_pdfs_are_skipped_with_a_notice_when_the_model_cannot_read_them(tmp_path):
    scanned, image = "https://funds.example/scan.pdf", "https://funds.example/chart.png"
    fetcher = FakeFetcher({scanned: ("application/pdf", minimal_pdf("")), image: ("image/png", b"\x89PNG")})
    llm = FakeLLM()

    result = make_run(tmp_path, ScrapeTask("report", (scanned, image, "https://funds.example/calls")), llm=llm, fetcher=fetcher).execute()
    assert [s["status"] for s in result["sources"]] == ["skipped", "skipped", "read"]
    assert len(result["notices"]) == 2 and all("multimodal = true" in n for n in result["notices"]) and llm.files == []

    # A vision model on an openai-compatible endpoint reads the image but not PDF pages.
    result = make_run(tmp_path, ScrapeTask("report", (scanned, image)), llm=llm, fetcher=fetcher, llm_toml=NVIDIA % "true").execute()
    assert [s["status"] for s in result["sources"]] == ["skipped", "read"]
    assert "export its pages as PNG/JPG" in result["sources"][0]["detail"] and llm.files == [("image/png", 4)]

    # Gemini takes the PDF itself.
    llm = FakeLLM()
    result = make_run(tmp_path, ScrapeTask("report", (scanned,)), llm=llm, fetcher=fetcher, llm_toml='[llm]\nprovider = "gemini"\n').execute()
    assert [s["status"] for s in result["sources"]] == ["read"] and llm.files[0][0] == "application/pdf"


def test_pdf_text_collapses_whitespace_and_reports_damaged_files():
    assert pdf_text(minimal_pdf("Net revenue was EUR 4.2 million.")) == "Net revenue was EUR 4.2 million."
    assert pdf_text(minimal_pdf("")) == ""
    with pytest.raises(AgentError, match="could not read the PDF"):
        pdf_text(b"not a pdf at all")


def test_progress_reports_each_step(tmp_path):
    steps = []
    make_run(tmp_path, ScrapeTask("calls", ("https://funds.example/calls",)), progress=steps.append).execute()
    assert steps == ["Reading https://funds.example/calls", "Extracting from 1 source(s) (1/1)"]


def test_run_options_pick_the_model_and_the_browser(tmp_path, monkeypatch):
    from startup_agent import scrape

    config = tmp_path / "config.toml"
    config.write_text('[llm]\ndefault = "nvidia"\n[llm.nvidia]\nprovider = "openai-compatible"\nendpoint = "https://x/v1"\n'
                      '[llm.gemini]\nprovider = "gemini"\n', encoding="utf-8")
    used = []

    def fake_build(settings, refresh):
        used.append((settings.llm.name, settings.crawl.browser, refresh))
        raise AgentError("stop here")

    monkeypatch.setattr(scrape, "build_agent", fake_build)
    agent = ScrapeAgent(AgentSettings.load(config))
    task = ScrapeTask("calls", ("https://funds.example/calls",))
    for options in ({}, {"llm": "gemini", "stealth": False, "refresh": True}):
        with pytest.raises(AgentError, match="stop here"):
            agent.run(task, **options)
    assert used == [("nvidia", True, False), ("gemini", False, True)]
    with pytest.raises(AgentError, match="unknown model"):
        agent.run(task, llm="gpt")
    with pytest.raises(AgentError, match="unknown scrape mode 'poems'"):
        agent.run(ScrapeTask("calls", mode="poems"))
    with pytest.raises(AgentError, match="give 1 to 8 sources"):
        agent.run([])


def run_sources(tmp_path, monkeypatch, tasks, llm):
    """ScrapeAgent.run on several sources with the fake agent of make_run."""
    from startup_agent import scrape

    template = make_run(tmp_path, tasks[0], llm=llm)
    fetcher = FakeFetcher()
    monkeypatch.setattr(scrape, "build_agent", lambda settings, refresh: (template.agent, fetcher))
    fetcher.close = lambda: None
    steps = []
    return ScrapeAgent(template.settings).run(tasks, steps.append), steps


def test_several_sources_run_in_turn_and_merge_into_one_result(tmp_path, monkeypatch):
    class PerSource(FakeLLM):
        def complete_json(self, *, system, user, schema):
            self.calls.append(system)
            if "Focus: funding a startup can apply for" in system:
                return EXTRACTION
            return {"summary": "One fund.", "gaps": ["No team listed."], "records": [
                {"kind": "investor", "title": "The Fund", "details": "", "website": "https://funds.example", "attributes": [],
                 "source_url": "https://funds.example/about", "quote": "The fund was founded in 2019 by the ministry."},
                {"kind": "funding_call", "title": "BLUE CALL 2026", "details": "", "website": "", "attributes": [],
                 "source_url": "https://funds.example/about", "quote": "founded in 2019"}]}

    llm = PerSource()
    tasks = [ScrapeTask("open calls", ("https://funds.example/calls",), mode="funding_calls", label="Calls"),
             ScrapeTask("who runs the fund", ("https://funds.example/about",), mode="startups", label="About"),
             ScrapeTask("news", ("https://funds.example/missing",), label="News")]
    result, steps = run_sources(tmp_path, monkeypatch, tasks, llm)

    assert [(g["label"], g["mode"], g["records"], g["error"]) for g in result["groups"]] == [
        ("Calls", "funding_calls", 2, None), ("About", "startups", 2, None), ("News", "general", 0, None)]
    assert [r["group"] for r in result["records"]] == ["Calls", "Calls", "About", "About"]
    assert [s["group"] for s in result["sources"]] == ["Calls", "About", "News"]
    assert "About: No team listed." in result["gaps"] and any(g.startswith("News: Nothing from") for g in result["gaps"])
    assert result["summary"] == "Calls: One open call. About: One fund."
    blue_call = result["records"][0]
    assert blue_call["also_in"] == ["About"] and result["records"][3]["also_in"] == ["Calls"]  # same kind, same name
    assert result["records"][2]["self_reported"] is True  # read on the fund's own site
    assert steps[0] == "Calls: Reading https://funds.example/calls" and any(s.startswith("About: ") for s in steps)
    assert "Focus: startups and companies" in llm.calls[1]  # each source with its own focus prompt


def test_a_failing_source_is_reported_while_the_others_go_on(tmp_path, monkeypatch):
    tasks = [ScrapeTask("open calls", ("https://funds.example/calls",), label="Calls"), ScrapeTask("fund news", label="News")]
    result, _ = run_sources(tmp_path, monkeypatch, tasks, FakeLLM())
    assert result["groups"][1]["error"].startswith("give at least one URL") and len(result["records"]) == 2
    assert any(g.startswith("News: nothing read (give at least one URL") for g in result["gaps"])

    with pytest.raises(AgentError, match="A: give at least one URL.*; B: give at least one URL"):
        run_sources(tmp_path, monkeypatch, [ScrapeTask("x", label="A"), ScrapeTask("y", label="B")], FakeLLM())


def test_focus_prompts_exist_for_every_mode():
    from startup_agent.scrape import MODES, system_prompt

    for mode in MODES:
        prompt = system_prompt(mode)
        assert prompt.startswith("You are the research analyst") and "Focus:" in prompt


def test_an_empty_goal_is_refused():
    with pytest.raises(AgentError, match="goal is empty"):
        ScrapeAgent(settings=SimpleNamespace()).run(ScrapeTask("  "))  # type: ignore[arg-type]


def test_file_type_goal_links_and_batches():
    assert file_type("https://x.example/a/Report.PDF?download=1") == "application/pdf"
    assert file_type("https://x.example/page") is None

    links = ["https://x.example/calls/blue-call", "https://x.example/about", "https://cdn.example/blue-call-guide.pdf", "mailto:a@x.example"]
    assert goal_links(links, "blue call", "https://x.example/calls") == ["https://cdn.example/blue-call-guide.pdf", "https://x.example/calls/blue-call"]

    docs = [SourceDocument(f"https://x.example/{i}", "", "a" * n, "news", "2026-10-17") for i, n in enumerate((60, 60, 150))]
    groups = batches(docs, 100)
    assert [[len(d.text) for d in g] for g in groups] == [[60], [60], [100]]


def test_an_answer_cut_off_at_max_tokens_is_asked_again_for_each_half(tmp_path):
    from startup_agent.llm import AnswerCutOff
    from startup_agent.scrape import split_documents

    class Budget(FakeLLM):
        def complete_json(self, *, system, user, schema):
            self.calls.append(user)
            if user.count("### ") > 1:
                raise AnswerCutOff("cut off")
            url = "https://funds.example/calls" if "Blue Call" in user else "https://funds.example/about"
            quote = "Blue Call 2026 closes on 30 March 2026" if "Blue Call" in user else "founded in 2019 by the ministry"
            return {"summary": "Part.", "gaps": [], "records": [
                {"kind": "other", "title": url, "details": "", "website": "", "attributes": [], "source_url": url, "quote": quote}]}

    llm, steps = Budget(), []
    urls = ("https://funds.example/calls", "https://funds.example/about")
    result = make_run(tmp_path, ScrapeTask("everything", urls), llm=llm, progress=steps.append).execute()
    assert [r["evidence"] for r in result["records"]] == ["page", "page"] and len(llm.calls) == 3
    assert "The answer was too long: asking again for 1 and 1 source part(s)" in steps and result["summary"] == "Part."

    doc = SourceDocument("https://x.example", "", "alpha beta gamma delta", "news", "2026-10-17")
    first, second = split_documents([doc])
    assert (first[0].text, second[0].text) == ("alpha beta", "gamma delta")

    class Always(FakeLLM):
        def complete_json(self, **kwargs):
            raise AnswerCutOff("cut off")

    with pytest.raises(AgentError, match="cut off"):  # nothing at all answered
        make_run(tmp_path, ScrapeTask("everything", urls), llm=Always()).execute()


def test_a_part_the_model_keeps_failing_on_is_a_gap_and_the_rest_is_kept(tmp_path):
    from startup_agent.llm import LLMTimeout

    class SlowOnAbout(FakeLLM):
        def complete_json(self, *, system, user, schema):
            self.calls.append(user)
            if "founded" in user:
                raise LLMTimeout("m didn't answer within 300 s, twice")
            return EXTRACTION if "Blue Call" in user else {"summary": "", "records": [], "gaps": []}

    steps = []
    llm = SlowOnAbout()
    urls = ("https://funds.example/calls", "https://funds.example/about")
    result = make_run(tmp_path, ScrapeTask("everything", urls), llm=llm, progress=steps.append).execute()
    assert len(result["records"]) == 2  # from the calls page
    assert any(g.startswith("Not extracted, the model failed on part of the text: https://funds.example/about") for g in result["gaps"])
    assert any(s.startswith("The answer was too slow") for s in steps)
    assert any("Blue Call" in call and "founded" not in call for call in llm.calls)  # the calls page alone, after the split
