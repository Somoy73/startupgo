# StartupGo scraper

Public page fetching and startup lead discovery. This package contains **no AI**. Turning leads into
evidence-backed, scored entries (TRL, BRL, Ocean Impact Readiness, next steps) is done by the separate
agent module in [`../Agent`](../Agent/README.md), which uses this package for fetching and discovery.

## Setup

This package is a member of the uv workspace in `Modules/` (shared lockfile and `Modules/.venv`):

```bash
cd Modules && uv sync --all-packages && cd Scraper
```

Run commands from `Modules/Scraper` with `uv run`. Don't run a plain `uv sync` here: it would remove
the Agent's packages from the shared environment.

## Configuration

`config.toml` (next to this README) sets request pacing and the optional Chrome browser:

```toml
[scraper]
timeout = 30.0
delay = 1.5        # minimum seconds between requests
browser = true     # render pages with Chrome; options in [browser]
```

Flags given on the command line override the file: `--delay`, `--timeout`, `--browser/--no-browser`,
`--driver`, `--stealth/--no-stealth`, `--headed`, `--chrome-version`. Use `--config PATH` to read a
different file. There are no secrets here. LLM credentials live in `../Agent/.env`.

## Usage

```bash
# Startups from a Wellfound collection page
uv run python main.py --source wellfound --url https://wellfound.com/startups/industry/aquaculture --limit 10

# Places matching a query via OpenStreetMap Nominatim
uv run python main.py --source osm --query "ocean technology" --location Lisbon --format csv --output leads.csv

# Generic directory page (JSON-LD and company/startup cards)
uv run python main.py --source generic --url https://example.org/startups
```

From Python:

```python
from scraper import AppSettings, StartupScraper, create_fetcher

fetcher = create_fetcher(AppSettings.load())   # config.toml, or defaults if absent
try:
    leads = StartupScraper(fetcher).collect(source="osm", query="ocean technology", location="Lisbon", limit=10)
finally:
    fetcher.close()
```

## Wellfound discovery

`--source wellfound` reads Wellfound startup **collection** pages, such as
`https://wellfound.com/startups/industry/aquaculture` or `/startups/location/finland`. It parses the
Apollo state embedded in the page's `__NEXT_DATA__` script, follows `?page=N` up to `--limit`, and
returns leads with name, website, one-line pitch, description, stage badge, market tags and location.

- `/search` is disallowed by Wellfound's robots.txt, and company pages sit behind a bot check, so only
  collection URLs are accepted.
- Unknown collections redirect to a generic list. The adapter detects that and raises instead of
  returning unrelated startups.
- Wellfound location tags mix cities and countries, so they go into `StartupLead.location`, not
  `country`.

```bash
uv run python main.py --source wellfound --url https://wellfound.com/startups/industry/aquaculture --limit 10
```

To turn leads into schema entries (facts, evidence, TRL/BRL/OIR, next steps), use the agent:
`cd ../Agent && uv run startup-agent discover --url <collection URL> --profile`.

## Browser mode (undetected-chromedriver + selenium-stealth)

JavaScript-rendered pages can be loaded through Chrome instead of plain HTTP.
Enable it with `browser = true` under `[scraper]` in `config.toml`, or pass `--browser`
(`--no-browser` turns it off for one run). Driver options live in the `[browser]` table:

| Key | Default | Meaning |
|-----|---------|---------|
| `driver` | `"undetected"` | `undetected` = undetected-chromedriver (patched driver binary); `selenium` = stock Selenium driver |
| `stealth` | `true` | Apply selenium-stealth (hides `navigator.webdriver`, consistent UA/platform/WebGL/languages) |
| `headless` | `true` | Run without a window |
| `chrome_version` | `0` | Chrome major version for undetected-chromedriver; `0` auto-detects |
| `settle_seconds` | `2.0` | Extra wait after the load event for client-side rendering |
| `user_data_dir` | `""` | Persistent Chrome profile (keeps cookie-consent choices between runs) |
| `virtual_display` | `false` | Linux only: headed Chrome inside Xvfb |

CLI overrides: `--driver`, `--stealth/--no-stealth`, `--headed`, `--chrome-version`.

```bash
uv run python main.py --source generic --url "https://example.org/startups" --browser --format json
```

Notes:

- undetected-chromedriver 3.5.x needs Python 3.11 (it imports `distutils`, removed in 3.12).
- If a page answers with a CAPTCHA / bot challenge / block page, the fetcher raises
  `ScraperError` and stops. It does not try to solve or bypass challenges, and it keeps the
  configured request delay. Check a site's terms and robots.txt before scraping it. LinkedIn
  and Glassdoor prohibit automated collection, so prefer official APIs or data exports there.

## Tests

```bash
uv run python -m unittest discover -s tests -t .
```
