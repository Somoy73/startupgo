#!/usr/bin/env python3
"""Export every table and view in the Startup Go database to CSV.

  python3 export_csv.py                 runtime DB (or $STARTUPGO_DB) -> Modules/DataAPIs/csv/<table>.csv
  python3 export_csv.py --with-payloads  also keep raw_fetches.payload (large JSON blobs; dropped by default)

`refresh.py snapshot` calls export() for the tracked snapshot, so the committed CSVs match the committed DB.
"""
from __future__ import annotations

import csv
import os
import sqlite3
import sys
from pathlib import Path

HERE = Path(__file__).parent
OUT = HERE / "csv"


def default_db() -> Path:
    return Path(os.environ.get("STARTUPGO_DB") or HERE.parents[1] / "DB" / "runtime" / "startupgo.db")


def export(db: Path, out: Path = OUT, with_payloads: bool = False, quiet: bool = False) -> dict[str, int]:
    """Write one CSV per table/view of ``db`` into ``out``; returns rows per table."""
    if not db.exists():
        sys.exit(f"{db} not found; run refresh.py or ingest.py first")
    out.mkdir(parents=True, exist_ok=True)
    conn = sqlite3.connect(f"file:{db}?mode=ro", uri=True)
    counts: dict[str, int] = {}
    names = [r[0] for r in conn.execute("SELECT name FROM sqlite_master WHERE type IN ('table','view') AND name NOT LIKE 'sqlite_%' ORDER BY type, name")]
    for name in names:
        cur = conn.execute(f'SELECT * FROM "{name}"')
        cols = [c[0] for c in cur.description]
        keep = [i for i, c in enumerate(cols) if not (name == "raw_fetches" and c == "payload" and not with_payloads)]
        rows = 0
        # utf-8-sig so Excel opens non-ASCII names (Lüderitz, Wärtsilä) correctly
        with open(out / f"{name}.csv", "w", newline="", encoding="utf-8-sig") as fh:
            w = csv.writer(fh)
            w.writerow([cols[i] for i in keep])
            for r in cur:
                w.writerow([r[i] for i in keep])
                rows += 1
        counts[name] = rows
        if not quiet:
            print(f"{name:28} {rows:6} rows")
    conn.close()
    return counts


def main(argv):
    export(default_db(), OUT, with_payloads="--with-payloads" in argv)


if __name__ == "__main__":
    main(sys.argv[1:])
