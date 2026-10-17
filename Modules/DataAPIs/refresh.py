#!/usr/bin/env python3
"""startup-refresh: the whole data pipeline as one command, writing only to the runtime DB.

  python3 refresh.py                          daily tier: free sources only (same as `run --tier daily`)
  python3 refresh.py run --tier full          also SerpApi, People Data Labs (credits) and a BlueInvest re-crawl
  python3 refresh.py run --steps cordis,features,gaps    selected steps only (see `steps`)
  python3 refresh.py steps                    list the steps of each tier
  python3 refresh.py status                   last runs and their steps
  python3 refresh.py init [--reset]           create the runtime DB from the tracked snapshot
  python3 refresh.py configs                  generate Agent/Search configs that point at the runtime DB
  python3 refresh.py snapshot                 runtime DB -> DB/startupgo.db + CSVs + GAPS.md, for committing

Files: the runtime DB, generated configs, the runtime search index and reports live in DB/runtime/ (untracked).
Tracked files (DB/startupgo.db, csv/, GAPS.md) change only through `snapshot`. Main's modules (Agent, Search,
Scraper) are not modified: they are driven through their own CLIs with generated --config files.
"""
from __future__ import annotations

import argparse
import importlib.util
import json
import os
import shutil
import sqlite3
import subprocess
import sys
import time
import tomllib
from collections.abc import Callable
from dataclasses import dataclass
from datetime import datetime, timedelta, timezone
from pathlib import Path

HERE = Path(__file__).parent
sys.path.insert(0, str(HERE))
import export_csv  # noqa: E402
import features  # noqa: E402
import ingest  # noqa: E402  (registers every scraper, loads .env)
import ingest_eu  # noqa: E402
import ingest_gaps  # noqa: E402

MODULES = HERE.parent
AGENT_DIR, SEARCH_DIR = MODULES / "Agent", MODULES / "Search"
STALE_LOCK = timedelta(hours=6)
WATCH = ("startup_signals", "funding_events", "eu_grants", "startup_people", "person_ventures", "startup_external_ids",
         "field_suggestions", "funding_opportunities", "market_indicators", "blueinvest_profiles", "patent_classes",
         "startup_external_peers", "startup_features", "startup_parameter_status", "raw_fetches")


class Skip(Exception):
    """Raised by a step that cannot run here (missing key, tool or package); the run continues."""


@dataclass
class Context:
    conn: sqlite3.Connection
    tier: str

    def startups(self, where: str = "1=1", args: tuple = ()) -> list[sqlite3.Row]:
        return self.conn.execute(f"SELECT * FROM startups WHERE {where} ORDER BY id", args).fetchall()


@dataclass
class Step:
    name: str
    tiers: tuple[str, ...]
    fn: Callable[[Context], str | None]
    help: str


# ---------------------------------------------------------------------------
# Steps: thin wrappers around the existing ingest / features functions
# ---------------------------------------------------------------------------
def _need(env: str) -> None:
    if not os.environ.get(env):
        raise Skip(f"{env} not set (Modules/DataAPIs/.env)")


def step_startups(ctx: Context):
    yc, _ = ingest.fetch(ctx.conn, "yc_oss_companies", None, kind="companies", name="all")
    paid = ctx.tier == "full"
    for st in ctx.startups():
        ingest.ingest_startup(ctx.conn, st, yc, paid=paid)
    return f"{len(ctx.startups())} startups ({'with' if paid else 'without'} paid lookups)"


def step_serpapi(ctx: Context):
    _need("SERPAPI_KEY")
    for st in ctx.startups():
        ingest.ingest_serpapi(ctx.conn, st)


def step_funding(ctx: Context):
    ingest.ingest_funding(ctx.conn)


def step_market(ctx: Context):
    ingest.ingest_market(ctx.conn)


def step_uk_filings(ctx: Context):
    _need("COMPANIES_HOUSE_KEY")
    if importlib.util.find_spec("pypdf") is None:
        raise Skip("pypdf not installed (uv sync --all-packages in Modules)")
    for st in ctx.startups():
        features.fetch_uk(ctx.conn, st)


def step_form_d(ctx: Context):
    for st in ctx.startups():
        features.fetch_form_d(ctx.conn, st)


def step_cordis(ctx: Context):
    for st in ctx.startups():
        ingest_eu.ingest_cordis(ctx.conn, st)


def step_patent_classes(ctx: Context):
    for st in ctx.startups():
        ingest_eu.ingest_patent_classes(ctx.conn, st)
    ingest_eu.retag_patent_classes(ctx.conn)


def step_blueinvest(ctx: Context):
    n = ingest_eu.crawl_blueinvest(ctx.conn, refresh=ctx.tier == "full")
    for st in ctx.startups():
        ingest_eu.match_blueinvest(ctx.conn, st)
    return f"{n} profiles ({'re-crawled' if ctx.tier == 'full' else 'cached list'})"


def step_registers(ctx: Context):
    for st in ctx.startups("country IN ('France','Norway')"):
        (ingest_eu.ingest_fr if st["country"] == "France" else ingest_eu.ingest_no)(ctx.conn, st)


def step_founders(ctx: Context):
    _need("PDL_API_KEY")
    for st in ctx.startups():
        uk = ctx.conn.execute("SELECT 1 FROM startup_people WHERE startup_id=? AND source_name='uk_companies_house_company' AND is_founder=1",
                              (st["id"],)).fetchone()
        if not uk:
            ingest_gaps.ingest_founders(ctx.conn, st)
    ctx.conn.execute("DELETE FROM people WHERE id NOT IN (SELECT person_id FROM startup_people)")
    ctx.conn.commit()


def step_jobs(ctx: Context):
    for st in ctx.startups():
        ingest_gaps.ingest_jobs(ctx.conn, st)


def step_peers(ctx: Context):
    ingest_gaps.ingest_peers(ctx.conn)


def step_features(ctx: Context):
    features.build_local(ctx.conn)
    features.compute(ctx.conn)
    return f"as_of {features.AS_OF}"


def step_gaps(ctx: Context):
    ingest.build_gaps(ctx.conn)


def step_agent(ctx: Context):
    cfg = write_configs()["agent"]
    env = {**_dotenv(AGENT_DIR / ".env"), **os.environ, "STARTUPGO_DB": str(ingest.db_path())}
    key = tomllib.loads(cfg.read_text(encoding="utf-8")).get("llm", {}).get("api_key_env", "GEMINI_API_KEY")
    if not env.get(key):
        raise Skip(f"Agent key missing: {key} in Modules/Agent/.env")
    if shutil.which("uv"):
        cmd = ["uv", "run", "--package", "startup-agent", "startup-agent", "--config", str(cfg), "pipeline"]
    elif importlib.util.find_spec("startup_agent"):
        cmd = [sys.executable, "-m", "startup_agent", "--config", str(cfg), "pipeline"]
    else:
        raise Skip("startup-agent not installed (uv sync --all-packages in Modules)")
    p = subprocess.run(cmd, cwd=MODULES, env=env, capture_output=True, text=True, timeout=4 * 3600)
    if p.returncode != 0:
        raise RuntimeError(f"startup-agent pipeline exited {p.returncode}: {(p.stderr or p.stdout)[-500:]}")
    return (p.stdout.strip().splitlines() or ["no candidates"])[-1][:200]


def step_search_index(ctx: Context):
    cfg = write_configs()["search"]
    env = {**_dotenv(SEARCH_DIR / ".env"), **os.environ, "STARTUPGO_DB": str(ingest.db_path())}
    if not (env.get("CHAT_API_KEY") and env.get("EMBEDDING_API_KEY")):
        raise Skip("Search keys missing: CHAT_API_KEY / EMBEDDING_API_KEY in Modules/Search/.env")
    if shutil.which("uv"):
        cmd = ["uv", "run", "--package", "startup-search", "process-storage", "--config", str(cfg)]
    elif importlib.util.find_spec("startup_search"):
        cmd = [sys.executable, "-m", "startup_search.process_storage", "--config", str(cfg)]
    else:
        raise Skip("startup-search not installed (uv sync --all-packages in Modules)")
    p = subprocess.run(cmd, cwd=MODULES, env=env, capture_output=True, text=True, timeout=3600)
    if p.returncode != 0:
        raise RuntimeError(f"process-storage exited {p.returncode}: {(p.stderr or p.stdout)[-500:]}")
    return (p.stdout.strip().splitlines() or ["indexed"])[-1][:200]


STEPS = [
    Step("startups", ("daily", "full"), step_startups, "registries, YC, patents, papers, news, HN, GitHub, Form D search, web history, Companies House; full: + PDL, SerpApi patents"),
    Step("serpapi", ("full",), step_serpapi, "Google search knowledge panel + Google Jobs (2 SerpApi searches per startup)"),
    Step("funding_opportunities", ("daily", "full"), step_funding, "EU calls (SEDIA), Grants.gov, UKRI projects, TED tenders"),
    Step("market", ("daily", "full"), step_market, "World Bank + Eurostat indicators"),
    Step("uk_filings", ("daily", "full"), step_uk_filings, "Companies House officers, appointments and SH01 share allotments"),
    Step("sec_form_d", ("daily", "full"), step_form_d, "SEC Form D offerings and related persons"),
    Step("cordis", ("daily", "full"), step_cordis, "EU grants per startup (CORDIS)"),
    Step("patent_classes", ("daily", "full"), step_patent_classes, "CPC classes and legal status of held patents"),
    Step("blueinvest", ("daily", "full"), step_blueinvest, "BlueInvest pipeline match (full: re-crawl the list)"),
    Step("national_registers", ("daily", "full"), step_registers, "French and Norwegian registers for startups in those countries"),
    Step("founders", ("full",), step_founders, "non-UK founders and boards via PDL person search (credits)"),
    Step("job_boards", ("daily", "full"), step_jobs, "open roles from the company's own job board"),
    Step("peers", ("daily", "full"), step_peers, "competitor universe from the BlueInvest pipeline"),
    Step("agent", ("full",), step_agent, "agent research + judge on startups without a recent agent entry and discovered leads (LLM calls)"),
    Step("features", ("daily", "full"), step_features, "funding timeline, investors, founders, grants, patents, risk features"),
    Step("gaps", ("daily", "full"), step_gaps, "parameter coverage per startup + GAPS.md (runtime copy)"),
    Step("search_index", ("daily", "full"), step_search_index, "rebuild the runtime LightRAG index with main's process-storage"),
]


# ---------------------------------------------------------------------------
# Run log + lock
# ---------------------------------------------------------------------------
def _now() -> str:
    return datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M:%S")


def _counts(conn: sqlite3.Connection) -> dict[str, int]:
    tables = {r[0] for r in conn.execute("SELECT name FROM sqlite_master WHERE type='table'")}
    return {t: conn.execute(f'SELECT COUNT(*) FROM "{t}"').fetchone()[0] for t in WATCH if t in tables}


def start_run(conn: sqlite3.Connection, kind: str, tier: str | None, trigger: str, force: bool = False) -> int:
    conn.commit()  # close any implicit transaction before taking the lock
    conn.execute("BEGIN IMMEDIATE")  # check-and-insert atomically: one run at a time
    try:
        row = conn.execute("SELECT id, started_at FROM refresh_runs WHERE status='running' ORDER BY id DESC LIMIT 1").fetchone()
        if row:
            started = datetime.strptime(row["started_at"], "%Y-%m-%d %H:%M:%S").replace(tzinfo=timezone.utc)
            if not force and datetime.now(timezone.utc) - started < STALE_LOCK:
                raise RuntimeError(f"run {row['id']} is still running (started {row['started_at']} UTC); use --force if it died")
            conn.execute("UPDATE refresh_runs SET status='error', finished_at=?, summary=? WHERE id=?",
                         (_now(), json.dumps({"error": "abandoned (lock taken over)"}), row["id"]))
        run_id = conn.execute("INSERT INTO refresh_runs (kind, tier, trigger, status, started_at) VALUES (?,?,?, 'running', ?)",
                              (kind, tier, trigger, _now())).lastrowid
        conn.execute("COMMIT")
    except Exception:
        conn.execute("ROLLBACK")
        raise
    return run_id


def run(tier: str = "daily", steps: list[str] | None = None, trigger: str = "cli", force: bool = False,
        step_table: list[Step] | None = None, conn: sqlite3.Connection | None = None, quiet: bool = False) -> tuple[int, str]:
    """Run the pipeline; returns (run_id, status). Each step's failure is recorded and the run continues."""
    table = step_table or STEPS
    todo = [s for s in table if (s.name in steps if steps else tier in s.tiers)]
    unknown = set(steps or []) - {s.name for s in table}
    if unknown:
        raise SystemExit(f"unknown step(s): {', '.join(sorted(unknown))}")
    conn = conn or ingest.open_db()
    run_id = start_run(conn, "refresh", tier, trigger, force)
    results: dict[str, str] = {}
    changes: dict[str, int] = {}
    for seq, step in enumerate(todo, 1):
        if not quiet:
            print(f"[{seq}/{len(todo)}] {step.name}: {step.help}", flush=True)
        conn.execute("INSERT INTO refresh_steps (run_id, step, seq, status, started_at) VALUES (?,?,?, 'running', ?)", (run_id, step.name, seq, _now()))
        conn.commit()  # progress is visible to readers (the backend status endpoint) while the step runs
        before, errs_before, t0 = _counts(conn), _fetch_errors(conn), time.monotonic()
        status, detail = "ok", None
        try:
            detail = step.fn(Context(conn, tier))
        except Skip as exc:
            status, detail = "skipped", str(exc)
        except Exception as exc:  # noqa: BLE001  (one broken source must not stop the run)
            status, detail = "error", f"{type(exc).__name__}: {exc}"[:1000]
            try:
                conn.rollback()
            except sqlite3.Error:
                pass
        after = _counts(conn)
        delta = {t: after[t] - before.get(t, 0) for t in after if after[t] != before.get(t, 0)}
        new_errors = _fetch_errors(conn) - errs_before
        if new_errors:
            delta["fetch_errors"] = new_errors
        for t, d in delta.items():
            changes[t] = changes.get(t, 0) + d
        conn.execute("UPDATE refresh_steps SET status=?, finished_at=?, duration_s=?, counts=?, detail=? WHERE run_id=? AND step=?",
                     (status, _now(), round(time.monotonic() - t0, 1), json.dumps(delta), detail, run_id, step.name))
        conn.commit()
        results[step.name] = status
        if not quiet:
            print(f"      -> {status}" + (f" ({detail})" if detail else ""), flush=True)
    final = "ok" if all(v in ("ok", "skipped") for v in results.values()) else ("error" if all(v == "error" for v in results.values()) else "partial")
    summary = {"steps": results, "changes": changes}
    conn.execute("UPDATE refresh_runs SET status=?, finished_at=?, summary=? WHERE id=?", (final, _now(), json.dumps(summary), run_id))
    conn.commit()
    return run_id, final


def _fetch_errors(conn: sqlite3.Connection) -> int:
    return conn.execute("SELECT COUNT(*) FROM raw_fetches WHERE status='error'").fetchone()[0]


def status(limit: int = 5) -> None:
    conn = ingest.open_db()
    for r in conn.execute("SELECT * FROM refresh_runs ORDER BY id DESC LIMIT ?", (limit,)).fetchall():
        print(f"run {r['id']}  {r['kind']}/{r['tier'] or '-'}  {r['status']:8} {r['started_at']} -> {r['finished_at'] or '…'}  ({r['trigger']})")
        for s in conn.execute("SELECT * FROM refresh_steps WHERE run_id=? ORDER BY seq", (r["id"],)):
            print(f"   {s['seq']:2}. {s['step']:22} {s['status']:8} {s['duration_s'] or 0:7.1f}s  {s['detail'] or ''}"[:160])


# ---------------------------------------------------------------------------
# Generated configs for main's Agent and Search (their tracked config.toml files are never edited)
# ---------------------------------------------------------------------------
def write_configs() -> dict[str, Path]:
    """Copy main's Agent/Search config.toml with only the paths changed, into DB/runtime/config/{agent,search}/.

    Both tools resolve paths and their .env from the config file's folder, so every path is written absolute and the
    folder gets a symlink to main's .env (no secrets are copied). Regenerated each time, so main's settings never drift.
    """
    out = ingest.RUNTIME_DIR / "config"
    agent = tomllib.loads((AGENT_DIR / "config.toml").read_text(encoding="utf-8"))
    paths = agent.setdefault("paths", {})
    for key, default in (("cache_dir", "cache"), ("system_prompt", "prompts/system.md"), ("section_prompt", "prompts/section.md"),
                         ("judge_prompt", "prompts/judge.md")):
        paths[key] = str((AGENT_DIR / paths.get(key, default)).resolve())  # shared cache: reruns cost nothing
    paths["output_dir"] = str((ingest.RUNTIME_DIR / "agent_output").resolve())
    agent.setdefault("database", {})["path"] = str(ingest.db_path().resolve())
    search = tomllib.loads((SEARCH_DIR / "config.toml").read_text(encoding="utf-8"))
    search.setdefault("storage", {})["working_dir"] = str((ingest.RUNTIME_DIR / "rag_storage").resolve())
    search.setdefault("sources", {}).update(database=str(ingest.db_path().resolve()),
                                            entries=str((ingest.RUNTIME_DIR / "agent_output" / "startups").resolve()))
    written = {}
    for name, data, src_dir in (("agent", agent, AGENT_DIR), ("search", search, SEARCH_DIR)):
        folder = out / name
        folder.mkdir(parents=True, exist_ok=True)
        path = folder / "config.toml"
        path.write_text(f"# Generated by Modules/DataAPIs/refresh.py from Modules/{src_dir.name}/config.toml; do not edit.\n"
                        + dump_toml(data), encoding="utf-8")
        link, target = folder / ".env", src_dir / ".env"
        if link.is_symlink() or link.exists():
            link.unlink()
        if target.exists():
            link.symlink_to(target.resolve())
        written[name] = path
    return written


def dump_toml(data: dict, prefix: str = "") -> str:
    """Minimal TOML writer for config files: tables, strings, numbers, booleans, (nested) lists, inline tables."""
    def key(k: str) -> str:
        return k if k.replace("_", "").replace("-", "").isalnum() and k.isascii() else json.dumps(k)

    def val(v) -> str:
        if isinstance(v, bool):
            return "true" if v else "false"
        if isinstance(v, (int, float)):
            return repr(v)
        if isinstance(v, str):
            return json.dumps(v, ensure_ascii=False)
        if isinstance(v, list):
            return "[" + ", ".join(val(x) for x in v) + "]"
        if isinstance(v, dict):
            return "{ " + ", ".join(f"{key(k)} = {val(x)}" for k, x in v.items()) + " }"
        raise TypeError(f"cannot write {type(v).__name__} to TOML")

    lines = [f"{key(k)} = {val(v)}" for k, v in data.items() if not isinstance(v, dict)]
    for k, v in data.items():
        if isinstance(v, dict):
            name = f"{prefix}{key(k)}"
            lines.append(f"\n[{name}]")
            lines.append(dump_toml(v, name + ".").rstrip("\n"))
    return "\n".join(x for x in lines if x is not None) + "\n"


def _dotenv(path: Path) -> dict[str, str]:
    if not path.exists():
        return {}
    out = {}
    for line in path.read_text(encoding="utf-8").splitlines():
        k, sep, v = line.strip().partition("=")
        if sep and k and not k.startswith("#"):
            out[k.strip()] = v.strip().strip("\"'")
    return out


# ---------------------------------------------------------------------------
# Snapshot: runtime -> tracked files (the only way tracked data changes)
# ---------------------------------------------------------------------------
def snapshot(csv_dir: Path | None = None, gaps_path: Path | None = None) -> Path:
    src, dst = ingest.db_path(), ingest.snapshot_path()
    if src.resolve() == dst.resolve():
        raise SystemExit("STARTUPGO_DB points at the snapshot itself; nothing to copy")
    if not src.exists():
        raise SystemExit(f"{src} does not exist; run `refresh.py init` or a refresh first")
    tmp = dst.with_suffix(".tmp")
    tmp.unlink(missing_ok=True)
    conn = sqlite3.connect(src)
    conn.execute("VACUUM INTO ?", (str(tmp),))  # compact, consistent copy without WAL files
    conn.close()
    os.replace(tmp, dst)
    snap = sqlite3.connect(dst)
    snap.row_factory = sqlite3.Row
    ingest.write_report(snap, path=gaps_path or HERE / "GAPS.md", source=ingest._rel(dst))
    snap.close()
    counts = export_csv.export(dst, csv_dir or export_csv.OUT, quiet=True)
    print(f"snapshot written: {ingest._rel(dst)} ({sum(counts.values())} rows in {len(counts)} tables/views), "
          f"CSVs in {ingest._rel(csv_dir or export_csv.OUT)}, GAPS.md updated. Review with `git status`, then commit.")
    return dst


def init(reset: bool = False) -> Path:
    path = ingest.db_path()
    if reset:
        for p in (path, path.with_name(path.name + "-wal"), path.with_name(path.name + "-shm")):
            p.unlink(missing_ok=True)
    conn = ingest.open_db(path)  # copies the snapshot when missing, applies migrations + schema
    conn.close()
    print(f"runtime DB ready: {ingest._rel(path)}")
    return path


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(prog="startup-refresh", description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    sub = parser.add_subparsers(dest="command")
    r = sub.add_parser("run", help="run the pipeline (default)")
    for p in (parser, r):
        p.add_argument("--tier", choices=("daily", "full"), default="daily")
        p.add_argument("--steps", help="comma-separated step names (overrides the tier's list)")
        p.add_argument("--trigger", choices=("cli", "api", "timer"), default="cli")
        p.add_argument("--force", action="store_true", help="take over a run lock older than the stale limit or still marked running")
    sub.add_parser("steps", help="list steps per tier")
    sub.add_parser("status", help="show recent runs")
    i = sub.add_parser("init", help="create the runtime DB from the tracked snapshot")
    i.add_argument("--reset", action="store_true", help="delete the runtime DB first")
    sub.add_parser("configs", help="generate Agent/Search configs for the runtime DB")
    sub.add_parser("snapshot", help="copy the runtime DB to the tracked snapshot, re-export CSVs and GAPS.md")
    args = parser.parse_args(argv)
    if args.command == "steps":
        for s in STEPS:
            print(f"{s.name:22} {'/'.join(s.tiers):11} {s.help}")
        return 0
    if args.command == "status":
        status()
        return 0
    if args.command == "init":
        init(args.reset)
        return 0
    if args.command == "configs":
        for name, path in write_configs().items():
            print(f"{name}: {ingest._rel(path)}")
        return 0
    if args.command == "snapshot":
        snapshot()
        return 0
    run_id, final = run(args.tier, args.steps.split(",") if args.steps else None, args.trigger, args.force)
    print(f"run {run_id}: {final}  (details: refresh.py status)")
    return 0 if final == "ok" else 1


if __name__ == "__main__":
    sys.exit(main())
