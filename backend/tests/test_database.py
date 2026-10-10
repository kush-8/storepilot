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


class ImportTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.directory = Path(self.temp.name)
        self.db = self.directory / "retail.db"
        self.source = ROOT.parent / "data"
        if not (self.source / "store_master.csv").exists():
            self.skipTest("Original ../data CSV package is absent; importer tests require it")

    def test_rebuild_has_same_counts_and_rejects_implicit_overwrite(self):
        result = build_database(self.source, self.db)
        self.assertEqual(result["total_rows"], 2970)
        with self.assertRaises(FileExistsError):
            build_database(self.source, self.db)
        rebuilt = build_database(self.source, self.db, replace=True)
        self.assertEqual(result["tables"], rebuilt["tables"])
        with sqlite3.connect(self.db) as connection:
            self.assertEqual(connection.execute("PRAGMA foreign_key_check").fetchall(), [])
            self.assertEqual(
                connection.execute("SELECT COUNT(*) FROM import_manifest").fetchone()[0], 9
            )

    def test_invalid_foreign_key_leaves_existing_database_intact(self):
        build_database(self.source, self.db)
        original = hashlib.sha256(self.db.read_bytes()).hexdigest()
        copied = self.directory / "data"
        shutil.copytree(self.source, copied)
        path = copied / "inventory.csv"
        with path.open(newline="", encoding="utf-8") as handle:
            reader = csv.DictReader(handle)
            headers = reader.fieldnames
            rows = list(reader)
        rows[0]["store_id"] = "UNKNOWN_STORE"
        with path.open("w", newline="", encoding="utf-8") as handle:
            writer = csv.DictWriter(handle, fieldnames=headers)
            writer.writeheader()
            writer.writerows(rows)
        with self.assertRaises(sqlite3.IntegrityError):
            build_database(copied, self.db, replace=True)
        self.assertEqual(hashlib.sha256(self.db.read_bytes()).hexdigest(), original)
        self.assertEqual(list(self.directory.glob(".import-*.db")), [])


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
