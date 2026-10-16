"""Command line: profile a startup, discover and profile leads, rescore an entry, export the schema."""

from __future__ import annotations

import argparse
import json
import sys
from collections.abc import Sequence
from pathlib import Path
from typing import Any

from .config import AgentSettings
from .errors import AgentError
from .factory import build_agent
from .graph import build_agent_graph
from .record import record_json_schema
from .store import RecordStore


def parse_args(argv: Sequence[str] | None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(prog="startup-agent", description=__doc__)
    parser.add_argument("--config", type=Path, default=Path("config.toml"))
    commands = parser.add_subparsers(dest="command", required=True)

    profile = commands.add_parser("profile", help="Build a schema entry from a startup's name and website")
    profile.add_argument("--name", required=True)
    profile.add_argument("--website", required=True)
    profile.add_argument("--business-id", help="Finnish Y-tunnus, if known")
    profile.add_argument("--url", action="append", default=[], help="Extra source page (press release, CORDIS record, ...); repeatable")
    profile.add_argument("--refresh", action="store_true", help="Ignore cached pages and LLM outputs")

    discover = commands.add_parser("discover", help="Find startups with the scraper, optionally profiling each")
    discover.add_argument("--source", default="wellfound", choices=("wellfound", "generic", "osm"))
    discover.add_argument("--url", help="Collection URL, e.g. https://wellfound.com/startups/industry/clean-technology")
    discover.add_argument("--query", help="Search query (osm source)")
    discover.add_argument("--location", default="")
    discover.add_argument("--limit", type=int, default=10)
    discover.add_argument("--profile", action="store_true", help="Profile every lead that has a website")
    discover.add_argument("--refresh", action="store_true")

    rescore = commands.add_parser("rescore", help="Recompute scores and next steps from an entry's facts (e.g. after manual edits)")
    rescore.add_argument("entry", type=Path)

    schema = commands.add_parser("schema", help="Print the JSON Schema of a startup entry")
    schema.add_argument("--output", type=Path)

    graph = commands.add_parser("graph", help="Run the LangGraph research, evaluation, or combined workflow")
    graph.add_argument("--mode", choices=("research", "evaluation", "both"), default="both")
    graph.add_argument("--name")
    graph.add_argument("--website")
    graph.add_argument("--business-id")
    graph.add_argument("--url", action="append", default=[], help="Extra source page; repeatable")
    graph.add_argument("--source", default="wellfound", choices=("wellfound", "generic", "osm"))
    graph.add_argument("--query", help="Search query for the osm source")
    graph.add_argument("--location", default="")
    graph.add_argument("--limit", type=int, default=10)
    graph.add_argument("--entry", action="append", type=Path, default=[], help="Existing JSON entry; repeatable")
    graph.add_argument("--refresh", action="store_true")
    return parser.parse_args(argv)


def main(argv: Sequence[str] | None = None) -> int:
    args = parse_args(argv)
    if args.command == "schema":
        return _write_json(record_json_schema(), args.output)

    try:
        settings = AgentSettings.load(args.config)
        store = RecordStore(settings.output_dir)
        if args.command == "rescore":
            _report(*store.save(store.load(args.entry), weights=settings.weights))
            return 0

        if args.command == "graph":
            agent, fetcher = build_agent(settings, refresh=args.refresh)
            try:
                try:
                    records = [json.loads(path.read_text(encoding="utf-8")) for path in args.entry]
                except (OSError, json.JSONDecodeError) as exc:
                    raise AgentError(f"could not read graph entry: {exc}") from exc
                initial = {
                    "mode": args.mode,
                    "name": args.name or "",
                    "website": args.website or "",
                    "business_id": args.business_id,
                    "extra_urls": args.url,
                    "source": args.source,
                    "url": args.url[0] if args.url else None,
                    "query": args.query,
                    "location": args.location,
                    "limit": args.limit,
                    "records": records,
                }
                result = build_agent_graph(agent, weights=settings.weights).invoke(initial)
                return _write_json(result, None)
            finally:
                fetcher.close()

        agent, fetcher = build_agent(settings, refresh=args.refresh)
        try:
            if args.command == "profile":
                record = agent.profile(name=args.name, website=args.website, business_id=args.business_id, extra_urls=args.url)
                _report(*store.save(record, weights=settings.weights))
                return 0

            leads = agent.discover(source=args.source, url=args.url, query=args.query, location=args.location, limit=args.limit)
            if not args.profile:
                return _write_json([{"name": l.name, "website": l.website, "tagline": l.tagline, "stage": l.stage, "location": l.location} for l in leads], None)
            failures = 0
            for lead in leads:
                try:
                    _report(*store.save(agent.profile_lead(lead), weights=settings.weights))
                except AgentError as exc:
                    failures += 1
                    print(f"skipped {lead.name}: {exc}", file=sys.stderr)
            return 1 if failures and failures == len(leads) else 0
        finally:
            fetcher.close()
    except AgentError as exc:
        print(f"error: {exc}", file=sys.stderr)
        return 1


def _level(score: dict[str, Any]) -> str:
    return f"{score['level']}/{score['scale']}" if score["level"] is not None else "unknown"


def _report(path: Path, entry: dict[str, Any]) -> None:
    scores = entry["scores"]
    print(
        f"{entry['name']}: TRL {_level(scores['trl'])}, BRL {_level(scores['brl'])}, "
        f"OIR {_level(scores['ocean_impact_readiness'])}, investment {scores['investment_score']}/5 "
        f"(confidence {scores['overall_confidence']}), {len(entry['rejected_extractions'])} rejected, "
        f"{len(entry['errors'])} errors → {path}"
    )


def _write_json(data: object, output: Path | None) -> int:
    text = json.dumps(data, indent=2, ensure_ascii=False)
    if output:
        output.write_text(text + "\n", encoding="utf-8")
    else:
        print(text)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
