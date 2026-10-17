"""SQLite connection handling for the unified database: DB/startupgo_unified.db (entities, facts, assessments).

The Backend reads through the views in DB/unified.sql (startups, readiness_assessments, funding_rounds, ...) and
writes the 3 tables.
"""

import os
import shutil
import sqlite3
from collections.abc import Iterator
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[2]
SQL_DIR = REPO_ROOT / "DB"
DEFAULT_DB_PATH = SQL_DIR / "startupgo_unified.db"
SCHEMA = SQL_DIR / "unified.sql"


def db_path() -> Path:
    return Path(os.environ.get("STARTUPGO_DB", DEFAULT_DB_PATH))


def connect(path: Path | None = None) -> sqlite3.Connection:
    conn = sqlite3.connect(path or db_path(), check_same_thread=False)
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA foreign_keys = ON")
    return conn


def init_db(path: Path | None = None) -> Path:
    """Copy DB/startupgo_unified.db to ``path`` if it doesn't exist yet, then apply DB/unified.sql.

    unified.sql creates missing tables and recreates the views, so view changes reach existing databases.
    """
    path = path or db_path()
    if not path.exists():
        path.parent.mkdir(parents=True, exist_ok=True)
        shutil.copyfile(DEFAULT_DB_PATH, path)
    conn = connect(path)
    try:
        tables = {r[0] for r in conn.execute("SELECT name FROM sqlite_master WHERE type = 'table'")}
        if "startups" in tables:
            raise RuntimeError(
                f"{path} has the older schema (a startups table): serve its 3-table copy instead, "
                "written by `python3 Modules/DataAPIs/unify.py --preview <path>`"
            )
        conn.executescript(SCHEMA.read_text())
        conn.commit()
    finally:
        conn.close()
    return path


def get_conn() -> Iterator[sqlite3.Connection]:
    """FastAPI dependency: one connection per request."""
    conn = connect()
    try:
        yield conn
    finally:
        conn.close()
