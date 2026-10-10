"""Check importer atomicity and repeatability against the actual input package."""

import csv
import hashlib
import shutil
import sqlite3
import tempfile
import unittest
from pathlib import Path

from scripts.import_csv import ROOT, build_database


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


if __name__ == "__main__":
    unittest.main()
