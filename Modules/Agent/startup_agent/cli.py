"""Command line: run the research/evaluation workflow, profile or discover startups, rescore, export the schema."""

from __future__ import annotations

import argparse
import json
import sys
from collections.abc import Sequence
from pathlib import Path
from typing import Any

from .config import AgentSettings
from .errors import AgentError
from .factory import build_agent, build_judge
from .graph import build_agent_graph
from .record import StartupRecord, record_json_schema
from .store import RecordStore


def parse_args(argv: Sequence[str] | None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(prog="startup-agent", description=__doc__)
    parser.add_argument("--config", type=Path, help="Settings file (default: Agent/config.toml)")
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

    graph = commands.add_parser("graph", help="Multi-agent workflow: research and evaluation agents, reviewed by a judge")
    graph.add_argument("--mode", choices=("research", "evaluation", "both"), default="both")
    target = graph.add_argument_group("research one startup")
    target.add_argument("--name")
    target.add_argument("--website")
    target.add_argument("--business-id")
    target.add_argument("--url", action="append", default=[], help="Extra source page; repeatable")
    discovery = graph.add_argument_group("or discover startups to research")
    discovery.add_argument("--source", default="wellfound", choices=("wellfound", "generic", "osm"))
    discovery.add_argument("--discover-url", help="Collection URL, e.g. https://wellfound.com/startups/industry/aquaculture")
    discovery.add_argument("--query", help="Search query (osm source)")
    discovery.add_argument("--location", default="")
    discovery.add_argument("--limit", type=int, default=10)
    graph.add_argument("--entry", action="append", type=Path, default=[],
                       help="Entry to evaluate (mode evaluation); repeatable; default: all saved entries")
    graph.add_argument("--json", action="store_true", help="Print the final workflow state as JSON")
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
            return _run_graph(args, settings, store)

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
            print(f"usage: {agent.usage.summary()}", file=sys.stderr)
    except AgentError as exc:
        print(f"error: {exc}", file=sys.stderr)
        return 1


def _run_graph(args: argparse.Namespace, settings: AgentSettings, store: RecordStore) -> int:
    if args.mode == "evaluation":
        paths = args.entry or store.entry_paths()
        try:
            records = [json.loads(path.read_text(encoding="utf-8")) for path in paths]
        except (OSError, json.JSONDecodeError) as exc:
            raise AgentError(f"could not read entry: {exc}") from exc
        if not records:
            raise AgentError(f"no entries to evaluate in {store.entries}; run research first or pass --entry")
    else:
        records = []
        if not (args.name and args.website) and not (args.discover_url or args.query):
            raise AgentError("research needs --name and --website, or --discover-url / --query to discover startups")

    initial = {
        "mode": args.mode,
        "name": args.name or "",
        "website": args.website or "",
        "business_id": args.business_id,
        "extra_urls": args.url,
        "source": args.source,
        "discover_url": args.discover_url,
        "query": args.query,
        "location": args.location,
        "limit": args.limit,
        "records": records,
    }
    agent, fetcher = build_agent(settings, refresh=args.refresh)
    try:
        workflow = build_agent_graph(agent, judge=build_judge(settings, agent), weights=settings.weights)
        result = workflow.invoke(initial)
    finally:
        fetcher.close()
        print(f"usage: {agent.usage.summary()}", file=sys.stderr)

    for review in result.get("reviews", []):
        print(_review_line(review))

    entries = result.get("evaluated") if args.mode != "research" else result.get("records")
    for entry in entries or []:
        _report(*store.save(StartupRecord.from_dict(entry), weights=settings.weights))
    for assessment in result.get("assessments", []):
        print(_assessment_line(assessment))
    for skipped in result.get("skipped", []):
        print(f"skipped {skipped['name']}: {skipped['reason']}", file=sys.stderr)
    for error in result.get("errors", []):
        print(f"error: {error}", file=sys.stderr)
    if args.json:
        _write_json(result, None)
    return 0 if entries else 1


def _review_line(review: dict[str, Any]) -> str:
    issues = review["issues"]
    shown = "; ".join(issues[:3]) + (f"; +{len(issues) - 3} more" if len(issues) > 3 else "")
    return f"judge · {review['stage']} round {review['round']} · {review['entry']}: {review['verdict']}" + (f" — {shown}" if shown else "")


def _assessment_line(a: dict[str, Any]) -> str:
    score = f"{a['investment_score']}/5" if a["investment_score"] is not None else "unscored"
    parts = [
        f"#{a['rank']} {a['name']}: investment {score} (confidence {a['confidence']})",
        f"TRL {a['trl'] or '?'} · BRL {a['brl'] or '?'} · OIR {a['ocean_impact_readiness'] or '?'}",
    ]
    if a["strengths"]:
        parts.append(f"strong: {', '.join(a['strengths'])}")
    if a["weaknesses"]:
        parts.append(f"weak: {', '.join(a['weaknesses'])}")
    if a["next_steps"]:
        parts.append(f"next: {a['next_steps'][0]}")
    if a["review_status"]:
        parts.append(f"judge: {a['review_status']}" + (f" ({a['open_issues']} open issues)" if a["open_issues"] else ""))
    return " | ".join(parts)


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
