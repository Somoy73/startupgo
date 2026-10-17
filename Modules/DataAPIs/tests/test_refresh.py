"""Refresh pipeline mechanics: runtime DB, run log, lock, snapshot and generated configs (no network)."""
import hashlib
import sqlite3
import sys
import tomllib
from datetime import datetime, timedelta, timezone
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
import ingest  # noqa: E402
import refresh  # noqa: E402
from refresh import Skip, Step  # noqa: E402


@pytest.fixture()
def dbs(tmp_path, monkeypatch):
    """A seeded snapshot and an empty runtime location, both in tmp."""
    snap, runtime = tmp_path / "snapshot.db", tmp_path / "runtime" / "startupgo.db"
    monkeypatch.setenv("STARTUPGO_SNAPSHOT_DB", str(snap))
    monkeypatch.setenv("STARTUPGO_DB", str(snap))
    ingest.open_db().close()  # path == snapshot -> built from schema.sql + seed.sql
    monkeypatch.setenv("STARTUPGO_DB", str(runtime))
    return snap, runtime


def count(path, table):
    with sqlite3.connect(path) as c:
        return c.execute(f"SELECT COUNT(*) FROM {table}").fetchone()[0]


def test_runtime_db_is_copied_from_snapshot(dbs):
    snap, runtime = dbs
    assert not runtime.exists()
    refresh.init()
    assert runtime.exists() and count(runtime, "startups") == count(snap, "startups") == 8


def test_init_reset_recreates(dbs):
    _, runtime = dbs
    refresh.init()
    with sqlite3.connect(runtime) as c:
        c.execute("DELETE FROM startups WHERE slug='notpla'")
    assert count(runtime, "startups") == 7
    refresh.init(reset=True)
    assert count(runtime, "startups") == 8


def add_signal(ctx):
    ctx.conn.execute("INSERT INTO startup_signals (startup_id, source_name, signal_type, title, match_confidence) "
                     "VALUES (1, 'job_boards', 'job', 'Engineer', 'high')")
    ctx.conn.commit()
    return "added one"


def boom(ctx):
    raise ValueError("source down")


def no_key(ctx):
    raise Skip("KEY not set")


STEPS = [Step("a", ("daily",), add_signal, ""), Step("b", ("daily",), boom, ""), Step("c", ("daily",), no_key, ""),
         Step("d", ("full",), add_signal, "full only")]


def test_run_logs_each_step_and_continues_after_errors(dbs):
    refresh.init()
    run_id, status = refresh.run("daily", step_table=STEPS, quiet=True)
    assert status == "partial"
    with sqlite3.connect(dbs[1]) as c:
        steps = c.execute("SELECT step, status, detail, counts FROM refresh_steps WHERE run_id=? ORDER BY seq", (run_id,)).fetchall()
        run = c.execute("SELECT status, finished_at FROM refresh_runs WHERE id=?", (run_id,)).fetchone()
    assert [(s[0], s[1]) for s in steps] == [("a", "ok"), ("b", "error"), ("c", "skipped")]  # d is full-tier only
    assert "source down" in steps[1][2] and steps[2][2] == "KEY not set"
    assert '"startup_signals": 1' in steps[0][3]
    assert run[0] == "partial" and run[1]


def test_selected_steps_override_tier(dbs):
    refresh.init()
    run_id, status = refresh.run("daily", steps=["d"], step_table=STEPS, quiet=True)
    assert status == "ok"
    with pytest.raises(SystemExit):
        refresh.run("daily", steps=["nope"], step_table=STEPS, quiet=True)


def test_lock_blocks_a_second_run(dbs):
    refresh.init()
    with sqlite3.connect(dbs[1]) as c:
        c.execute("INSERT INTO refresh_runs (kind, tier, status, started_at) VALUES ('refresh','daily','running', ?)",
                  (datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M:%S"),))
    with pytest.raises(RuntimeError, match="still running"):
        refresh.run("daily", step_table=STEPS[:1], quiet=True)
    _, status = refresh.run("daily", step_table=STEPS[:1], force=True, quiet=True)
    assert status == "ok"
    with sqlite3.connect(dbs[1]) as c:
        assert c.execute("SELECT status FROM refresh_runs ORDER BY id LIMIT 1").fetchone()[0] == "error"  # taken over


def test_stale_lock_is_taken_over(dbs):
    refresh.init()
    old = (datetime.now(timezone.utc) - timedelta(hours=7)).strftime("%Y-%m-%d %H:%M:%S")
    with sqlite3.connect(dbs[1]) as c:
        c.execute("INSERT INTO refresh_runs (kind, tier, status, started_at) VALUES ('refresh','daily','running', ?)", (old,))
    assert refresh.run("daily", step_table=STEPS[:1], quiet=True)[1] == "ok"


def test_snapshot_copies_runtime_and_writes_reports(dbs, tmp_path):
    snap, runtime = dbs
    refresh.init()
    with sqlite3.connect(runtime) as c:
        c.execute("UPDATE startups SET website='https://www.seaforester.org' WHERE slug='seaforester'")
    assert count(snap, "startups") == 8
    refresh.snapshot(csv_dir=tmp_path / "csv", gaps_path=tmp_path / "GAPS.md")
    with sqlite3.connect(snap) as c:
        assert c.execute("SELECT website FROM startups WHERE slug='seaforester'").fetchone()[0] == "https://www.seaforester.org"
    assert (tmp_path / "csv" / "startups.csv").exists() and (tmp_path / "GAPS.md").exists()
    assert not snap.with_suffix(".tmp").exists()


def test_refresh_never_writes_the_snapshot(dbs):
    snap, _ = dbs
    before = hashlib.sha256(snap.read_bytes()).hexdigest()
    refresh.init()
    refresh.run("daily", step_table=STEPS, quiet=True)
    assert hashlib.sha256(snap.read_bytes()).hexdigest() == before


def test_generated_configs_change_only_paths(dbs, tmp_path, monkeypatch):
    monkeypatch.setattr(ingest, "RUNTIME_DIR", tmp_path / "rt")
    tracked = {p: hashlib.sha256(p.read_bytes()).hexdigest() for p in (refresh.AGENT_DIR / "config.toml", refresh.SEARCH_DIR / "config.toml")}
    out = refresh.write_configs()
    agent, search = (tomllib.loads(out[k].read_text()) for k in ("agent", "search"))
    orig_agent = tomllib.loads((refresh.AGENT_DIR / "config.toml").read_text())
    orig_search = tomllib.loads((refresh.SEARCH_DIR / "config.toml").read_text())
    assert {k: v for k, v in agent.items() if k != "paths"} == {k: v for k, v in orig_agent.items() if k != "paths"}
    assert all(Path(v).is_absolute() for v in agent["paths"].values())
    assert agent["paths"]["output_dir"].startswith(str((tmp_path / "rt").resolve()))
    assert Path(agent["paths"]["system_prompt"]).exists()
    assert search["sources"]["database"] == str(dbs[1].resolve())
    assert search["storage"]["working_dir"].startswith(str((tmp_path / "rt").resolve()))
    assert {k: v for k, v in search.items() if k not in ("sources", "storage")} == {k: v for k, v in orig_search.items() if k not in ("sources", "storage")}
    assert {p: hashlib.sha256(p.read_bytes()).hexdigest() for p in tracked} == tracked  # main's files untouched


def test_dump_toml_round_trips_mains_configs():
    for path in (refresh.AGENT_DIR / "config.toml", refresh.SEARCH_DIR / "config.toml"):
        data = tomllib.loads(path.read_text())
        assert tomllib.loads(refresh.dump_toml(data)) == data
