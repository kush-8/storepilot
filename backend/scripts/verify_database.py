"""Verify the retained SQLite snapshot without requiring removed operational CSVs."""

from __future__ import annotations

import argparse
import json
import re
import sqlite3
from contextlib import closing
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
TABLES = (
    "store_master",
    "vendor_master",
    "product_master",
    "employee_master",
    "inventory",
    "receipts",
    "returns_quality",
    "support_cases",
    "escalation_matrix",
)


def verify(database: Path) -> dict:
    uri = database.resolve().as_uri() + "?mode=ro"
    counts = {}
    with closing(sqlite3.connect(uri, uri=True)) as connection:
        if connection.execute("PRAGMA integrity_check").fetchall() != [("ok",)]:
            raise ValueError("Database integrity failed")
        if connection.execute("PRAGMA foreign_key_check").fetchall():
            raise ValueError("Foreign key validation failed")
        for table in TABLES:
            count = connection.execute(f'SELECT COUNT(*) FROM "{table}"').fetchone()[0]
            manifest = connection.execute(
                "SELECT row_count, source_sha256 FROM import_manifest WHERE table_name = ?",
                (table,),
            ).fetchone()
            if not manifest or manifest[0] != count:
                raise ValueError(f"{table}: row count differs from retained import manifest")
            if not re.fullmatch(r"[0-9a-f]{64}", manifest[1] or ""):
                raise ValueError(f"{table}: invalid source provenance hash")
            counts[table] = count
        stock = connection.execute(
            "SELECT on_hand, system_qty FROM inventory WHERE store_id=? AND sku=?",
            ("ST002", "SKU1001"),
        ).fetchone()
        if stock != (0, 4):
            raise ValueError("Seeded stock discrepancy evidence is missing")
        warehouse = connection.execute(
            "SELECT store_id, on_hand FROM inventory WHERE sku = ? AND store_id IN (?, ?)",
            ("SKU7001", "ST005", "WH001"),
        ).fetchall()
        if dict(warehouse) != {"ST005": 0, "WH001": 0}:
            raise ValueError("Seeded tennis-ball stock-out evidence is missing")
    return {"verified": True, "tables": counts, "total_rows": sum(counts.values())}


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--db", type=Path, default=ROOT / "database/retail.db")
    args = parser.parse_args()
    try:
        result = verify(args.db)
    except (OSError, ValueError, sqlite3.Error) as exc:
        parser.exit(1, f"Verification failed: {exc}\n")
    print(json.dumps(result, indent=2))


if __name__ == "__main__":
    main()
