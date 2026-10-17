"""SQLite connection handling and first-run initialisation from DB/schema.sql + DB/seed.sql."""

import os
import sqlite3
from collections.abc import Iterator
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[2]
SQL_DIR = REPO_ROOT / "DB"
DEFAULT_DB_PATH = SQL_DIR / "startupgo.db"


def db_path() -> Path:
    return Path(os.environ.get("STARTUPGO_DB", DEFAULT_DB_PATH))


def connect(path: Path | None = None) -> sqlite3.Connection:
    conn = sqlite3.connect(path or db_path(), check_same_thread=False)
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA foreign_keys = ON")
    return conn


def init_db(path: Path | None = None, *, reset: bool = False) -> Path:
    """Create the database from schema.sql and load seed.sql if it doesn't exist yet.

    schema.sql is all CREATE ... IF NOT EXISTS, so it is re-applied to an existing database to add new tables.
    """
    path = path or db_path()
    if reset and path.exists():
        path.unlink()
    fresh = not path.exists()
    conn = connect(path)
    try:
        migrate(conn)
        conn.executescript((SQL_DIR / "schema.sql").read_text())
        if fresh:
            conn.executescript((SQL_DIR / "seed.sql").read_text())
        conn.commit()
    finally:
        conn.close()
    return path


def migrate(conn: sqlite3.Connection) -> None:
    """Add columns schema.sql gained since the database was created (CREATE IF NOT EXISTS cannot alter tables).

    Modules/DataAPIs/ingest.py migrate() does the same for the runtime database.
    """
    tables = {r[0] for r in conn.execute("SELECT name FROM sqlite_master WHERE type='table'")}
    if "startups" in tables and "agent_researched_at" not in {r[1] for r in conn.execute("PRAGMA table_info(startups)")}:
        conn.execute("ALTER TABLE startups ADD COLUMN agent_researched_at TEXT")
        if "agent_entries" in tables:  # runs before the column existed: the stored entries
            conn.execute("UPDATE startups SET agent_researched_at = (SELECT stored_at FROM agent_entries e WHERE e.startup_id = startups.id)")


def get_conn() -> Iterator[sqlite3.Connection]:
    """FastAPI dependency: one connection per request."""
    conn = connect()
    try:
        yield conn
    finally:
        conn.close()
