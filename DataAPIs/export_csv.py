#!/usr/bin/env python3
"""Export every table and view in the Startup Go database to CSV.

  python3 export_csv.py                 -> DataAPIs/csv/<table>.csv
  python3 export_csv.py --with-payloads  also keep raw_fetches.payload (large JSON blobs; dropped by default)
"""
from __future__ import annotations

import csv
import os
import sqlite3
import sys
from pathlib import Path

HERE = Path(__file__).parent
DB_PATH = Path(os.environ.get("STARTUPGO_DB", HERE.parent / "DB" / "startupgo.db"))
OUT = HERE / "csv"


def main(argv):
    if not DB_PATH.exists():
        sys.exit(f"{DB_PATH} not found; run ingest.py first")
    OUT.mkdir(exist_ok=True)
    conn = sqlite3.connect(DB_PATH)
    names = [r[0] for r in conn.execute("SELECT name FROM sqlite_master WHERE type IN ('table','view') AND name NOT LIKE 'sqlite_%' ORDER BY type, name")]
    for name in names:
        cur = conn.execute(f'SELECT * FROM "{name}"')
        cols = [c[0] for c in cur.description]
        keep = [i for i, c in enumerate(cols) if not (name == "raw_fetches" and c == "payload" and "--with-payloads" not in argv)]
        rows = 0
        # utf-8-sig so Excel opens non-ASCII names (Lüderitz, Wärtsilä) correctly
        with open(OUT / f"{name}.csv", "w", newline="", encoding="utf-8-sig") as fh:
            w = csv.writer(fh)
            w.writerow([cols[i] for i in keep])
            for r in cur:
                w.writerow([r[i] for i in keep])
                rows += 1
        print(f"{name:28} {rows:6} rows")


if __name__ == "__main__":
    main(sys.argv[1:])
