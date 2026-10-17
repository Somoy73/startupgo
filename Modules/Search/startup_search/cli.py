"""Command line: search, inspect what ProcessStorage processes, check the models.

Processing itself is `process-storage` (startup_search/process_storage.py).
"""

from __future__ import annotations

import argparse
import asyncio
import json
import logging
import sys
import time
from collections.abc import Sequence
from dataclasses import asdict
from pathlib import Path

from .config import QUERY_MODES, SearchSettings
from .documents import load_documents
from .errors import SearchError
from .search import StartupSearch


def parse_args(argv: Sequence[str] | None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(prog="startup-search", description=__doc__)
    parser.add_argument("--config", type=Path, help="Settings file (default: Search/config.toml)")
    parser.add_argument("--verbose", action="store_true", help="Show LightRAG's progress log")
    commands = parser.add_subparsers(dest="command", required=True)

    documents = commands.add_parser("documents", help="Print the documents process-storage turns into storage, best first (no model calls)")
    documents.add_argument("--id", help="Print one document's full text, e.g. startup:notpla")

    query = commands.add_parser("query", help="Search the processed startups")
    query.add_argument("text")
    query.add_argument("--mode", choices=QUERY_MODES, help="LightRAG retrieval mode (default: [query] mode)")
    query.add_argument("--limit", type=int)
    query.add_argument("--json", action="store_true")

    commands.add_parser("check", help="One small call to the chat and embedding models; prints the real embedding size")
    return parser.parse_args(argv)


def main(argv: Sequence[str] | None = None) -> int:
    args = parse_args(argv)
    logging.basicConfig(level=logging.WARNING, format="%(levelname)s %(name)s: %(message)s")
    logging.getLogger("lightrag").setLevel(logging.INFO if args.verbose else logging.WARNING)
    try:
        settings = SearchSettings.load(args.config)
        if args.command == "documents":
            return _documents(settings, args.id)
        return asyncio.run(COMMANDS[args.command](settings, args))
    except SearchError as exc:
        print(f"error: {exc}", file=sys.stderr)
        return 2


def _documents(settings: SearchSettings, doc_id: str | None) -> int:
    documents = load_documents(settings.database, settings.entries, settings.kinds)
    if doc_id:
        match = next((d for d in documents if d.id == doc_id), None)
        if match is None:
            raise SearchError(f"no document {doc_id}")
        print(match.text)
        return 0
    for rank, doc in enumerate(documents, 1):  # in processing order: process-storage --limit N takes the first N
        link = f" -> {doc.key}" if doc.entry and doc.key else ""
        print(f"{rank:>4}  {doc.id:<40} {len(doc.text):>6} chars  {doc.name}{link}")
    return 0


async def _query(settings: SearchSettings, args: argparse.Namespace) -> int:
    search = StartupSearch(settings)
    try:
        matches = await search.search(args.text, mode=args.mode, limit=args.limit)
    finally:
        await search.close()
    if args.json:
        print(json.dumps([asdict(m) for m in matches], indent=2, ensure_ascii=False))
        return 0
    for match in matches:
        where = match.key if match.kind != "entry" else f"agent entry {match.entry}"
        terms = f"  matched: {', '.join(match.matched)}" if match.matched else ""
        print(f"{match.relevance:5.2f}  {match.name} ({where}){terms}")
    if not matches:
        print("no matches")
    return 0


async def _check(settings: SearchSettings, _: argparse.Namespace) -> int:
    """One small call to each model; the embedding size must match EMBEDDING_DIM."""
    from .nvidia import chat_model, embedding_model

    chat, embedding = settings.chat, settings.embedding
    started = time.monotonic()
    answer = await chat_model(chat, chat.require_key())("Reply with the single word: ok")
    print(f"chat {chat.model}: {answer.strip()[:40]!r} in {time.monotonic() - started:.1f}s")

    embed = embedding_model(embedding, embedding.require_key())
    started = time.monotonic()
    vectors = await embed.func(["seaweed packaging startup"], context="query")  # unchecked, to see the real size
    size = vectors.shape[-1]
    print(f"embedding {embedding.model}: {size} dimensions in {time.monotonic() - started:.1f}s")
    if size != embedding.dim:
        print(f"set EMBEDDING_DIM={size} in Search/.env (it is {embedding.dim})", file=sys.stderr)
        return 1
    return 0


COMMANDS = {"query": _query, "check": _check}


if __name__ == "__main__":
    raise SystemExit(main())
