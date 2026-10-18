"""The scrape agent: read public pages, PDFs and images for one or several goals and return source-checked records.

    ScrapeAgent().run(ScrapeTask(goal, urls, mode="funding_calls"))      one source
    ScrapeAgent().run([ScrapeTask(...), ScrapeTask(...)], llm="gemini")  several at once: one browser, one merged result
        ->  {summary, groups, records, gaps, sources, notices, model, usage}

Pages are loaded through the scraper (stealth Chrome unless ``stealth`` is off; cached, robots.txt respected).
Without URLs a source's goal is web-searched ([search] in config.toml) and the hits are read. A PDF's own text
layer is read directly (pypdf); images, and PDFs without a text layer, are transcribed by the model when it reads
files ([llm] multimodal, or Gemini). The LLM then turns the text into records, following prompts/scrape/system.md
and the source's focus prompt (prompts/scrape/<mode>.md). Code checks each record's verbatim quote against the text
it came from (found in the source, in a transcript, or not at all), marks what a company says on its own site as
self-reported, and links records that several sources describe (``also_in``).

Page text carries no link targets, so a startup or company read without a website is looked up in the links of the
page it came from: a link named after it that leaves the site is its website; one that stays on the site is its
profile page, which is opened (up to MAX_PROFILES per source) and read for the website and the fields the listing lacks.
"""

from __future__ import annotations

import io
import re
from collections.abc import Callable, Sequence
from dataclasses import dataclass, replace
from datetime import date
from pathlib import Path
from typing import Any
from urllib.parse import urldefrag, urlsplit

from pypdf import PdfReader
from scraper.errors import ScraperError

from .agent import SEARCH_SKIP_DOMAINS
from .config import AgentSettings
from .crawler import PageSkipped
from .documents import Link, SourceDocument, classify_source, host, locate_quote, same_site
from .errors import AgentError
from .factory import build_agent
from .llm import AnswerCutOff, LLMTimeout, QuotaExhausted

FILE_TYPES = {".pdf": "application/pdf", ".png": "image/png", ".jpg": "image/jpeg", ".jpeg": "image/jpeg", ".webp": "image/webp"}
PROMPTS = Path(__file__).resolve().parents[1] / "prompts" / "scrape"
# A source's focus: prompts/scrape/<mode>.md, added to prompts/scrape/system.md.
MODES = ("general", "startups", "funding_calls", "projects", "funding_rounds", "company", "document")
KINDS = ("startup", "company", "funding_call", "project", "funding_round", "investor", "figure", "other")
MIN_TEXT_CHARS = 40  # a page or file with less readable text than this is reported as empty
MAX_SOURCES = 8
MAX_SPLITS = 3  # an answer cut off at max_tokens, or too slow, is asked again for half the documents, up to this many times
MAX_PROFILES = 20  # profile pages opened per source to find websites the listing page doesn't link
PROFILE_KINDS = ("startup", "company", "investor")  # records whose own website is looked up on their profile page
RECORD_FIELDS = {"kind", "title", "details", "website", "source_url", "quote"}  # not repeated as attributes

SCHEMA: dict[str, Any] = {
    "type": "object",
    "additionalProperties": False,
    "required": ["summary", "records", "gaps"],
    "properties": {
        "summary": {"type": "string"},
        "records": {
            "type": "array",
            "items": {
                "type": "object",
                "additionalProperties": False,
                "required": ["kind", "title", "details", "website", "attributes", "source_url", "quote"],
                "properties": {
                    "kind": {"type": "string", "enum": list(KINDS)},
                    "title": {"type": "string"},
                    "details": {"type": "string"},
                    "website": {"type": "string"},
                    "attributes": {
                        "type": "array",
                        "items": {
                            "type": "object",
                            "additionalProperties": False,
                            "required": ["name", "value"],
                            "properties": {"name": {"type": "string"}, "value": {"type": "string"}},
                        },
                    },
                    "source_url": {"type": "string"},
                    "quote": {"type": "string"},
                },
            },
        },
        "gaps": {"type": "array", "items": {"type": "string"}},
    },
}
TRANSCRIBE = (
    "Transcribe the text, tables and figure captions of this document that matter for the request below. "
    "Plain text, numbers and names exactly as written, no summary and no commentary.\n\nRequest: {goal}"
)

Progress = Callable[[str], None]


class NeedsMultimodal(AgentError):
    """An image or scanned PDF was found, but the configured model isn't set up to read it."""


@dataclass(frozen=True, slots=True)
class ScrapeTask:
    """One source: what to get, where (no URLs: web-search the goal), and which focus prompt reads it."""

    goal: str
    urls: tuple[str, ...] = ()
    follow_links: bool = False  # also read the links on those pages that match the goal (including PDFs)
    max_pages: int = 8  # pages read for this source, searched and followed ones included (profile pages are extra)
    mode: str = "general"  # focus prompt, one of MODES
    label: str = ""  # the source's name in a merged result, e.g. "CORDIS ocean projects"


def system_prompt(mode: str) -> str:
    """The scrape agent's instructions for a source: the system prompt plus the mode's focus."""
    if mode not in MODES:
        raise AgentError(f"unknown scrape mode {mode!r}: one of {', '.join(MODES)}")
    return "\n\n".join((PROMPTS / f"{name}.md").read_text(encoding="utf-8").strip() for name in ("system", mode))


class ScrapeAgent:
    def __init__(self, settings: AgentSettings | None = None):
        self.settings = settings or AgentSettings.load()

    def run(self, tasks: ScrapeTask | Sequence[ScrapeTask], progress: Progress = lambda message: None, *, stealth: bool = True,
            llm: str | None = None, refresh: bool = False) -> dict[str, Any]:
        """Read one source, or several in turn with one browser and model, into one result.

        ``stealth`` renders pages in the stealth Chrome ([browser] in config.toml; False = plain HTTP), ``llm`` picks the
        model profile ([llm.<name>], e.g. "nvidia" or "gemini"; None = the default), ``refresh`` ignores the cache.
        A source that fails is reported in ``groups`` while the others go on; with one source, or when all fail, it raises.
        """
        tasks = [tasks] if isinstance(tasks, ScrapeTask) else list(tasks)
        if not tasks or len(tasks) > MAX_SOURCES:
            raise AgentError(f"give 1 to {MAX_SOURCES} sources, not {len(tasks)}")
        for task in tasks:
            if not task.goal.strip():
                raise AgentError(f"say what the agent should get{f' from {task.label}' if task.label else ''}: the goal is empty")
            system_prompt(task.mode)  # unknown modes fail before anything is fetched
        settings = self.settings.with_llm(llm)
        settings = replace(settings, crawl=replace(settings.crawl, browser=stealth))
        agent, fetcher = build_agent(settings, refresh=refresh)
        several = len(tasks) > 1
        labels = [task.label or (f"Source {i}" if several else "") for i, task in enumerate(tasks, 1)]
        runs: list[tuple[ScrapeTask, str, dict[str, Any] | None, str | None]] = []
        try:
            for task, label in zip(tasks, labels):
                say = (lambda message, label=label: progress(f"{label}: {message}")) if several else progress
                try:
                    runs.append((task, label, _Run(agent, fetcher, settings, task, say).execute(), None))
                except AgentError as exc:
                    if not several:
                        raise
                    runs.append((task, label, None, str(exc)))
                    say(f"stopped: {exc}")
        finally:
            fetcher.close()
        if all(result is None for _, _, result, _ in runs):
            raise AgentError("; ".join(f"{label}: {error}" for _, label, _, error in runs))
        return {**merge(runs), "model": settings.llm.model, "usage": agent.usage.summary()}


def merge(runs: Sequence[tuple[ScrapeTask, str, dict[str, Any] | None, str | None]]) -> dict[str, Any]:
    """The sources' results as one: records, sources and gaps tagged with their source; records that several sources
    describe (same website domain, or same kind and name) list the others in ``also_in``."""
    several = len(runs) > 1
    groups, records, gaps, sources, notices = [], [], [], [], []
    for task, label, result, error in runs:
        result = result or {"summary": "", "records": [], "gaps": [], "sources": [], "notices": []}
        groups.append({"label": label, "goal": task.goal, "mode": task.mode, "summary": result["summary"],
                       "records": len(result["records"]), "error": error})
        records += [{**r, "group": label} for r in result["records"]]
        sources += [{**s, "group": label} for s in result["sources"]]
        gaps += [f"{label}: {g}" if several else g for g in result["gaps"]]
        if error:
            gaps.append(f"{label}: nothing read ({error})")
        notices += result["notices"]
    for record in records:
        record["also_in"] = sorted({other["group"] for other in records if other["group"] != record["group"] and same_thing(record, other)})
    summary = " ".join(f"{g['label']}: {g['summary']}" if several else g["summary"] for g in groups if g["summary"])
    return {"goal": runs[0][0].goal, "summary": summary, "groups": groups, "records": records, "gaps": list(dict.fromkeys(gaps)),
            "sources": sources, "notices": list(dict.fromkeys(notices))}


def same_thing(a: dict[str, Any], b: dict[str, Any]) -> bool:
    """Whether two records describe the same thing: the same website domain, or the same kind and name."""
    if a["website"] and b["website"] and host(a["website"]) == host(b["website"]):
        return True
    return a["kind"] == b["kind"] and _name_key(a["title"]) == _name_key(b["title"]) != ""


def _name_key(name: str) -> str:
    """A name without case, punctuation and legal suffixes, so "Acme Ocean Oy" and "ACME OCEAN" compare equal."""
    words = re.findall(r"[a-z0-9]+", name.casefold())
    return " ".join(w for w in words if w not in {"oy", "oyj", "ab", "as", "gmbh", "ltd", "limited", "inc", "sa", "sas", "bv", "srl", "spa", "llc"})


def file_type(url: str) -> str | None:
    """The media type a URL's file extension points to, for the files the agent can read."""
    path = urlsplit(url).path.lower()
    return next((mime for ext, mime in FILE_TYPES.items() if path.endswith(ext)), None)


def pdf_text(data: bytes) -> str:
    """The text layer of a PDF, whitespace collapsed; empty for a scanned document."""
    try:
        reader = PdfReader(io.BytesIO(data))
        return " ".join(" ".join((page.extract_text() or "") for page in reader.pages).split())
    except Exception as exc:  # pypdf raises many error types for damaged files
        raise AgentError(f"could not read the PDF: {exc}") from exc


def clean_url(url: str) -> str:
    url = url.strip()
    return urldefrag(url if "://" in url else f"https://{url}")[0]


def goal_links(links: list[str], goal: str, origin: str) -> list[str]:
    """Links of the origin's site (or PDFs and images anywhere) whose URL mentions a word of the goal, best first."""
    words = set(re.findall(r"[a-z0-9]{4,}", goal.lower()))
    scored: dict[str, int] = {}
    for link in links:
        parts = urlsplit(link)
        is_file = file_type(link) is not None
        if parts.scheme not in ("http", "https") or not (is_file or same_site(link, host(origin))):
            continue
        hits = sum(word in f"{parts.path}?{parts.query}".lower() for word in words)
        if hits:
            scored.setdefault(link, hits + is_file)
    return sorted(scored, key=lambda link: (-scored[link], len(link)))


def _social(link: str) -> bool:
    h = host(link)
    return any(h == d or h.endswith("." + d) for d in SEARCH_SKIP_DOMAINS)


def _site_link(link: str) -> bool:
    """A web page link that isn't a file or a social or directory profile (which isn't anyone's own website)."""
    return urlsplit(link).scheme in ("http", "https") and file_type(link) is None and not _social(link)


_TAGLINE = re.compile(r"\s*[–—|:]\s*|\s+-\s*|-\s+")  # "Coral Rescue - Coral Restoration ...", "OW-Ferment- From waste to food"


def _names(link: str, name: str) -> bool:
    """Whether a link is named after the record: its text (or the text before a tagline) is the name, or its last path
    segment is the name as a slug."""
    key = _name_key(name)
    text = getattr(link, "text", "")
    slug = urlsplit(link).path.rstrip("/").rsplit("/", 1)[-1]
    return key != "" and key in (_name_key(text), _name_key(_TAGLINE.split(text, 1)[0]), _name_key(slug))


def social_link(name: str, links: Sequence[str]) -> str:
    """The record's social profile (LinkedIn, Instagram, ...) among a page's links, named after it; "" when none."""
    return next((str(link) for link in links if _social(link) and _names(link, name)), "")


def website_link(name: str, links: Sequence[str], page: str) -> str:
    """The record's own website among a page's links: a link off the page's site whose text is the record's name, or
    whose domain is the name (acmeocean.fi or acme-ocean.com for "Acme Ocean"); "" when none."""
    compact = _name_key(name).replace(" ", "")
    for link in links:
        if not _site_link(link) or same_site(link, host(page)):
            continue
        labels = {label.replace("-", "") for label in host(link).split(".")[:-1]}
        if _names(link, name) or (len(compact) >= 4 and compact in labels):
            parts = urlsplit(link)
            return f"{parts.scheme}://{parts.netloc}{parts.path or '/'}"
    return ""


def profile_link(name: str, links: Sequence[str], page: str) -> str:
    """The record's profile page among a page's links: a link on the page's own site named after the record; "" when none."""
    return next((clean_url(link) for link in links if _site_link(link) and same_site(link, host(page)) and clean_url(link) != page
                 and _names(link, name)), "")


def with_links(doc: SourceDocument, links: Sequence[str], skip: set[str]) -> SourceDocument:
    """The document with its off-site links (except those in ``skip``) written after its text, so the model sees
    where a "Website" or "Visit site" link leads."""
    shown = {str(link): getattr(link, "text", "") for link in links
             if _site_link(link) and not same_site(link, host(doc.url)) and link not in skip}
    if not shown:
        return doc
    return replace(doc, text=f"{doc.text}\n\nLinks on this page: " + "; ".join(f"{text or 'link'} <{url}>" for url, text in list(shown.items())[:30]))


def _fill(record: dict[str, Any], found: dict[str, Any], profile: str) -> None:
    """Complete a listing's record with what its profile page says: the website and the fields it lacked, and the
    company's name when the profile names the company behind a project-titled listing."""
    if not record["website"] and found["website"] and _site_link(found["website"]) and not same_site(found["website"], host(profile)):
        record["website"] = found["website"]
    names = {a["name"] for a in record["attributes"]}
    if "company" not in names and _name_key(record["title"]) not in _name_key(found["title"]):
        record["attributes"].append({"name": "company", "value": found["title"]})
        names.add("company")
    record["attributes"] += [a for a in found["attributes"] if a["name"] not in names]


def batches(documents: list[SourceDocument], budget: int) -> list[list[SourceDocument]]:
    """Documents grouped so that each group's text fits one LLM call; a longer document is cut to the budget."""
    groups: list[list[SourceDocument]] = []
    used = budget
    for doc in documents:
        text = doc.text[:budget]
        if used + len(text) > budget:
            groups.append([])
            used = 0
        groups[-1].append(doc if text == doc.text else replace(doc, text=text))
        used += len(text)
    return groups


def split_documents(group: list[SourceDocument]) -> tuple[list[SourceDocument], list[SourceDocument]]:
    """Two halves of a document group: half the documents each, or one document's text cut at a space near its middle."""
    if len(group) > 1:
        return group[: len(group) // 2], group[len(group) // 2:]
    doc = group[0]
    cut = doc.text.rfind(" ", 0, len(doc.text) // 2 + 1)
    cut = cut if cut > 0 else len(doc.text) // 2
    return [replace(doc, text=doc.text[:cut])], [replace(doc, text=doc.text[cut:].lstrip())]


class _Run:
    def __init__(self, agent: Any, fetcher: Any, settings: AgentSettings, task: ScrapeTask, progress: Progress):
        self.agent, self.fetcher, self.settings, self.task, self.progress = agent, fetcher, settings, task, progress
        self.documents: list[SourceDocument] = []
        self.transcripts: set[str] = set()  # URLs whose text is the model's transcript of an image or scanned PDF
        self.sources: list[dict[str, str]] = []
        self.notices: list[str] = []
        self.seen: set[str] = set()
        self.links: dict[str, list[Link]] = {}  # each read page's links

    # --- reading ------------------------------------------------------------------------

    def execute(self) -> dict[str, Any]:
        """This source's summary, records, gaps, sources and notices."""
        urls = [clean_url(u) for u in self.task.urls if u.strip()] or self._search()
        follow: list[str] = []
        for url in urls:
            links = self._read(url)
            if self.task.follow_links:
                follow += goal_links(links, self.task.goal, url)
        for url in dict.fromkeys(follow):  # read() stops at max_pages
            self._read(url)
        result = self._extract()
        result["gaps"] += self._find_websites(result["records"])
        gaps = result["gaps"] + [f"Nothing from {s['url']}: {s['detail']}" for s in self.sources if s["status"] != "read"]
        return {**result, "gaps": list(dict.fromkeys(gaps)), "sources": self.sources, "notices": self.notices}

    def _budget_left(self) -> int:
        return self.task.max_pages - len(self.sources)

    def _search(self) -> list[str]:
        searcher = self.agent.searcher
        if searcher is None:
            raise AgentError('give at least one URL: web search is off ([search] provider = "none" in config.toml)')
        self.progress(f"Searching the web for: {self.task.goal}")
        try:
            hits = [h.url for h in searcher.search(self.task.goal, limit=self.task.max_pages)]
        except QuotaExhausted as exc:
            raise AgentError(f"web search is unavailable: its quota is used up (Gemini's Google Search needs billing on the free tier). Give URLs instead. {str(exc)[:80]}") from exc
        urls = [u for u in hits if not any(host(u) == d or host(u).endswith("." + d) for d in SEARCH_SKIP_DOMAINS)]
        if not urls:
            raise AgentError("web search found no readable pages for that goal: give URLs, or word the goal differently")
        return urls

    def _read(self, url: str, *, budgeted: bool = True) -> list[Link]:
        """Load one page, PDF or image into the documents; returns the page's links."""
        if url in self.seen or (budgeted and self._budget_left() <= 0):
            return []
        self.seen.add(url)
        mime = file_type(url)
        self.progress(f"Reading {url}")
        try:
            if mime:
                doc, links = self._read_file(url, mime), []
            else:
                doc, links = self.agent.loader.load(url, source_type=classify_source(url, ""), readable=True)
        except (PageSkipped, NeedsMultimodal) as exc:
            self._source(url, "skipped", str(exc), mime)
            return []
        except (ScraperError, AgentError) as exc:
            self._source(url, "error", str(exc), mime)
            return []
        if len(doc.text) < MIN_TEXT_CHARS:
            self._source(url, "empty", "the model found no readable text in the file" if mime else
                         "no readable text (a login wall, or a page that only shows content to a signed-in user?)", mime)
            return []
        self.documents.append(doc)
        self.links[url] = links
        self._source(url, "read", doc.title, mime)
        return links

    def _source(self, url: str, status: str, detail: str, mime: str | None) -> None:
        self.sources.append({"url": url, "kind": "pdf" if mime == "application/pdf" else "image" if mime else "page", "status": status, "detail": detail})

    def _read_file(self, url: str, mime: str) -> SourceDocument:
        """A PDF's own text; for an image or a scanned PDF, what the model reads in it."""
        content_type, data = self.fetcher.fetch_file(url)
        mime = content_type or mime
        text = pdf_text(data) if mime == "application/pdf" else ""
        if len(text) < MIN_TEXT_CHARS:
            text = self._ask_model(url, data, mime)
            self.transcripts.add(url)
        title = urlsplit(url).path.rsplit("/", 1)[-1]
        return SourceDocument(url, title, text[: self.settings.crawl.section_chars], classify_source(url, ""), date.today().isoformat())

    def _ask_model(self, url: str, data: bytes, mime: str) -> str:
        llm = self.settings.llm
        scanned = mime == "application/pdf"
        # Only Gemini takes PDF pages; openai-compatible endpoints take images, and the agent doesn't render pages.
        if not llm.reads_images or (scanned and llm.provider != "gemini"):
            what = "a scanned PDF without a text layer" if scanned else "an image"
            fix = ('export its pages as PNG/JPG, or use [llm] provider = "gemini"' if scanned and llm.reads_images
                   else 'set [llm] multimodal = true for a vision model (e.g. NVIDIA Nemotron VL), or provider = "gemini"')
            note = f"{url} is {what}, which the model {llm.model} is not set up to read: {fix} in Modules/Agent/config.toml."
            if note not in self.notices:
                self.notices.append(note)
            raise NeedsMultimodal(note)
        return self.agent.extractor.llm.transcribe(TRANSCRIBE.format(goal=self.task.goal), data=data, mime=mime)

    # --- websites -----------------------------------------------------------------------

    def _find_websites(self, records: list[dict[str, Any]]) -> list[str]:
        """Fill in the websites of startups and companies the page text didn't give: a link named after the record that
        leaves its page's site is the website; one that stays is the record's profile page, opened and read for it.
        Returns the gaps left."""
        missing = [r for r in records if not r["website"] and r["kind"] in PROFILE_KINDS]
        profiles: dict[str, dict[str, Any]] = {}
        for record in missing:
            page = record["source_url"] if record["source_url"] in self.links else ""
            pages = [page] if page else list(self.links)
            for url in pages:
                if website := website_link(record["title"], self.links[url], url):
                    record["website"] = website
                    break
                profile = profile_link(record["title"], self.links[url], url)
                if profile and profile not in profiles and len(profiles) < MAX_PROFILES:
                    profiles[profile] = record
                    break
        if profiles:
            self._read_profiles(profiles)
        for record in missing:
            # Only a LinkedIn or Instagram page: shown so the website can be looked up, but never the website itself
            # (startups are told apart by their website's domain).
            pages = [record["source_url"]] if record["source_url"] in self.links else list(self.links)
            social = next((s for url in pages if (s := social_link(record["title"], self.links[url]))), "")
            if not record["website"] and social and all(a["name"] != "social_profile" for a in record["attributes"]):
                record["attributes"].append({"name": "social_profile", "value": social})
        unfound = [r["title"] for r in missing if not r["website"]]
        if not unfound:
            return []
        names = ", ".join(unfound[:10]) + (f" and {len(unfound) - 10} more" if len(unfound) > 10 else "")
        return [f"No website found for {len(unfound)} of {len(missing)} startups/companies without one on the page ({names}): check their profile pages or a company registry."]

    def _read_profiles(self, profiles: dict[str, dict[str, Any]]) -> None:
        """Open the profile pages and take each record's website and missing fields from them."""
        self.progress(f"Opening {len(profiles)} profile page(s) to find websites the listing doesn't link")
        listing = {str(link) for page_links in self.links.values() for link in page_links}  # navigation and footer links
        new: list[SourceDocument] = []
        for url, record in profiles.items():
            fresh = url not in self.seen
            self._read(url, budgeted=False)
            if url not in self.links:
                continue
            record["attributes"].append({"name": "profile_page", "value": url})
            if website := website_link(record["title"], self.links[url], url):
                record["website"] = website
            if fresh:
                doc = next(d for d in self.documents if d.url == url)
                new.append(with_links(doc, self.links[url], listing))
        if not new:
            return
        found: dict[str, list[dict[str, Any]]] = {}
        system = system_prompt(self.task.mode)
        for group in batches(new, self.settings.crawl.section_chars):
            self.progress(f"Extracting from {len(group)} profile page(s)")
            for part, out in self._ask(system, group, []):  # a profile the model fails on just keeps the listing's record
                for raw in out.get("records", []):
                    record = self._check(raw, part)
                    if record["source_url"] in profiles and record["kind"] in PROFILE_KINDS:
                        found.setdefault(record["source_url"], []).append(record)
        for url, candidates in found.items():
            # A profile page can list related companies too: the one named like the listing's record, else the first.
            record = profiles[url]
            _fill(record, next((c for c in candidates if _name_key(c["title"]) == _name_key(record["title"])), candidates[0]), url)

    # --- extraction ---------------------------------------------------------------------

    def _extract(self) -> dict[str, Any]:
        if not self.documents:
            return {"summary": "", "records": [], "gaps": ["No page could be read, so there was nothing to extract."]}
        system = system_prompt(self.task.mode)
        groups = batches(self.documents, self.settings.crawl.section_chars)
        summaries: list[str] = []
        records: dict[tuple[str, str], dict[str, Any]] = {}
        gaps: list[str] = []
        answered = 0
        failures: list[str] = []
        for i, group in enumerate(groups, 1):
            self.progress(f"Extracting from {len(group)} source(s) ({i}/{len(groups)})")
            for part, out in self._ask(system, group, failures):
                answered += 1
                summaries.append(str(out.get("summary", "")).strip())
                gaps += [str(g) for g in out.get("gaps", [])]
                for raw in out.get("records", []):
                    record = self._check(raw, part)
                    records.setdefault((record["title"].casefold(), record["source_url"]), record)
        if not answered:
            raise AgentError(failures[0])
        gaps += [f"Not extracted, the model failed on part of the text: {f}" for f in dict.fromkeys(failures)]
        return {"summary": " ".join(dict.fromkeys(s for s in summaries if s)), "records": list(records.values()), "gaps": gaps}

    def _ask(self, system: str, group: list[SourceDocument], failures: list[str],
             splits: int = 0) -> list[tuple[list[SourceDocument], dict[str, Any]]]:
        """The model's answer for these documents. An answer cut off at max_tokens, or one that timed out, is asked again
        for each half; a part that still fails is added to ``failures`` and skipped, so the other parts are kept."""
        pages = "\n\n".join(f"### {d.url}\n{d.title}\n{d.text}" for d in group)
        try:
            return [(group, self.agent.extractor.llm.complete_json(system=system, user=f"Request: {self.task.goal}\n\nDocuments:\n\n{pages}",
                                                                   schema=SCHEMA))]
        except (AnswerCutOff, LLMTimeout) as exc:
            if splits >= MAX_SPLITS:
                failures.append(f"{', '.join(dict.fromkeys(d.url for d in group))}: {exc}")
                return []
            why = "too long" if isinstance(exc, AnswerCutOff) else "too slow"
        halves = split_documents(group)
        self.progress(f"The answer was {why}: asking again for {len(halves[0])} and {len(halves[1])} source part(s)")
        return [answer for half in halves for answer in self._ask(system, half, failures, splits + 1)]

    def _check(self, raw: dict[str, Any], group: list[SourceDocument]) -> dict[str, Any]:
        """The record with its quote checked in code (found in the source's own text, in a transcript, or not found),
        and whether it is self-reported: read on the record's own website, so a claim rather than independent evidence."""
        doc, _ = locate_quote(str(raw.get("quote", "")), group, raw.get("source_url"))
        source_url = doc.url if doc else str(raw.get("source_url", ""))
        website = str(raw.get("website", "")).strip()
        website = clean_url(website) if website and "." in website and " " not in website else ""
        kind = raw.get("kind") if raw.get("kind") in KINDS else "other"
        return {
            "kind": kind,
            "title": str(raw.get("title", "")).strip(),
            "details": str(raw.get("details", "")).strip(),
            "website": website,
            "attributes": [{"name": a["name"], "value": a["value"]} for a in raw.get("attributes", [])
                           if a.get("name") and a.get("value") and a["name"] not in RECORD_FIELDS],
            "source_url": source_url,
            "quote": str(raw.get("quote", "")).strip(),
            "evidence": "unverified" if doc is None else "transcript" if doc.url in self.transcripts else "page",
            "self_reported": bool(website and source_url) and same_site(source_url, host(website)),
        }
