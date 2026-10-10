"""Verify source hashes, transformed rows, foreign keys, and SQLite integrity."""

from __future__ import annotations

import argparse
import json
import sqlite3
from contextlib import closing
from pathlib import Path

from import_csv import ROOT, TABLES, read_rows


def verify(data_dir: Path, database: Path) -> dict:
    uri = database.resolve().as_uri() + "?mode=ro"
    counts = {}
    with closing(sqlite3.connect(uri, uri=True)) as connection:
        if connection.execute("PRAGMA integrity_check").fetchone()[0] != "ok":
            raise ValueError("Database integrity failed")
        if connection.execute("PRAGMA foreign_key_check").fetchall():
            raise ValueError("Foreign key validation failed")
        for table in TABLES:
            columns = [(r[1], r[2]) for r in connection.execute(f'PRAGMA table_info("{table}")')]
            rows, digest = read_rows(data_dir / f"{table}.csv", columns)
            actual = connection.execute(f'SELECT * FROM "{table}"').fetchall()
            if sorted(actual, key=repr) != sorted(rows, key=repr):
                raise ValueError(f"{table}: database rows differ from converted source rows")
            manifest = connection.execute(
                "SELECT row_count, source_sha256 FROM import_manifest WHERE table_name = ?",
                (table,),
            ).fetchone()
            if manifest != (len(rows), digest):
                raise ValueError(f"{table}: import manifest does not match source")
            counts[table] = len(actual)
        warehouse = connection.execute(
            "SELECT store_id, on_hand FROM inventory WHERE sku = ? AND store_id IN (?, ?)",
            ("SKU7001", "ST005", "WH001"),
        ).fetchall()
        if dict(warehouse) != {"ST005": 0, "WH001": 0}:
            raise ValueError("Seeded tennis-ball stock-out evidence is missing")
    return {"verified": True, "tables": counts, "total_rows": sum(counts.values())}


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--data-dir", type=Path, default=ROOT.parent / "data")
    parser.add_argument("--db", type=Path, default=ROOT / "database/retail.db")
    args = parser.parse_args()
    try:
        result = verify(args.data_dir, args.db)
    except (OSError, ValueError, sqlite3.Error) as exc:
        parser.exit(1, f"Verification failed: {exc}\n")
    print(json.dumps(result, indent=2))


if __name__ == "__main__":
    main()
