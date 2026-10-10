"""Validate the retained SQLite source snapshot without requiring operational CSVs."""

import sqlite3
from contextlib import closing

from tests.support import BACKEND

TABLE_COUNTS = {
    "store_master": 50,
    "vendor_master": 15,
    "product_master": 520,
    "employee_master": 100,
    "inventory": 1250,
    "receipts": 310,
    "returns_quality": 160,
    "support_cases": 550,
    "escalation_matrix": 15,
}


def snapshot_connection():
    uri = (BACKEND / "database" / "retail.db").resolve().as_uri() + "?mode=ro"
    return closing(sqlite3.connect(uri, uri=True))


def test_snapshot_integrity_table_counts_and_import_provenance():
    with snapshot_connection() as connection:
        assert connection.execute("PRAGMA integrity_check").fetchone()[0] == "ok"
        assert connection.execute("PRAGMA foreign_key_check").fetchall() == []
        manifest = {
            table: count
            for table, count in connection.execute(
                "SELECT table_name, row_count FROM import_manifest"
            )
        }
        assert manifest == TABLE_COUNTS
        actual = {
            table: connection.execute(f'SELECT COUNT(*) FROM "{table}"').fetchone()[0]
            for table in TABLE_COUNTS
        }
        assert actual == TABLE_COUNTS and sum(actual.values()) == 2970


def test_snapshot_preserves_seeded_stockout_evidence():
    with snapshot_connection() as connection:
        assert connection.execute(
            "SELECT on_hand, system_qty FROM inventory WHERE store_id=? AND sku=?",
            ("ST002", "SKU1001"),
        ).fetchone() == (0, 4)
        warehouse_stock = connection.execute(
            "SELECT store_id, on_hand FROM inventory WHERE sku=? AND store_id IN (?, ?)",
            ("SKU7001", "ST005", "WH001"),
        ).fetchall()
        assert dict(warehouse_stock) == {"ST005": 0, "WH001": 0}
