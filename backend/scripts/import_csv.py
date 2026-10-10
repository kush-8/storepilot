"""Atomically build the retail SQLite database from the nine source CSVs.

Uses only the Python standard library. Run from any working directory.
"""

from __future__ import annotations

import argparse
import csv
import hashlib
import io
import json
import os
import sqlite3
import tempfile
from contextlib import closing
from datetime import date, datetime, timezone
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
TABLES = (
    "store_master", "vendor_master", "product_master", "employee_master",
    "inventory", "receipts", "returns_quality", "support_cases", "escalation_matrix",
)
BOOL_COLUMNS = {"high_demand", "quality_check_ok", "receipt_present", "human_approval_required"}
DATE_COLUMNS = {"effective_from", "last_count_date", "receipt_date"}


def convert(value: str | None, column: str, sql_type: str) -> object:
    if value is None:
        raise ValueError(f"Missing value for {column}")
    if value == "":
        return None
    if column in BOOL_COLUMNS:
        if value not in {"Yes", "No"}:
            raise ValueError(f"Expected Yes/No for {column}, got {value!r}")
        return int(value == "Yes")
    if column in DATE_COLUMNS:
        return date.fromisoformat(value).isoformat()
    if column == "created_ts":
        parsed = datetime.fromisoformat(value)
        if parsed.tzinfo is not None:
            raise ValueError("Source timestamps must be naive local IST times")
        return parsed.isoformat(sep=" ", timespec="seconds")
    if sql_type == "INTEGER":
        return int(value)
    if sql_type == "REAL":
        return float(value)
    return value


def read_rows(path: Path, columns: list[tuple[str, str]]) -> tuple[list[tuple], str]:
    # Read one snapshot so the stored hash describes exactly the imported bytes.
    raw = path.read_bytes()
    content = raw.decode("utf-8-sig")
    reader = csv.DictReader(io.StringIO(content, newline=""))
    expected = [name for name, _ in columns]
    if reader.fieldnames != expected:
        raise ValueError(f"{path.name}: expected headers {expected}, got {reader.fieldnames}")
    rows = []
    for line, row in enumerate(reader, start=2):
        if None in row:
            raise ValueError(f"{path.name}:{line}: unexpected extra fields")
        try:
            rows.append(tuple(convert(row[name], name, kind) for name, kind in columns))
        except (ValueError, TypeError) as exc:
            raise ValueError(f"{path.name}:{line}: {exc}") from exc
    return rows, hashlib.sha256(raw).hexdigest()


def build_database(data_dir: Path, destination: Path, *, replace: bool = False) -> dict:
    destination = destination.resolve()
    if destination.exists() and not replace:
        raise FileExistsError(f"{destination} already exists; use --replace to rebuild it")
    destination.parent.mkdir(parents=True, exist_ok=True)
    descriptor, temporary_name = tempfile.mkstemp(
        prefix=".import-", suffix=".db", dir=destination.parent
    )
    os.close(descriptor)
    temporary = Path(temporary_name)
    counts = {}
    try:
        with closing(sqlite3.connect(temporary)) as connection:
            connection.executescript((ROOT / "database/schema.sql").read_text(encoding="utf-8"))
            connection.execute("BEGIN")
            imported_at = datetime.now(timezone.utc).isoformat()
            for table in TABLES:
                info = connection.execute(f'PRAGMA table_info("{table}")').fetchall()
                columns = [(entry[1], entry[2]) for entry in info]
                source = data_dir / f"{table}.csv"
                rows, digest = read_rows(source, columns)
                placeholders = ",".join("?" for _ in columns)
                connection.executemany(f'INSERT INTO "{table}" VALUES ({placeholders})', rows)
                counts[table] = len(rows)
                connection.execute(
                    "INSERT INTO import_manifest VALUES (?, ?, ?, ?, ?)",
                    (table, source.name, len(rows), digest, imported_at),
                )
            violations = connection.execute("PRAGMA foreign_key_check").fetchall()
            if violations:
                raise ValueError(f"Foreign key violations: {violations}")
            connection.commit()
            integrity = connection.execute("PRAGMA integrity_check").fetchone()[0]
            if integrity != "ok":
                raise ValueError(f"SQLite integrity check failed: {integrity}")
        # Publish only after all inserts, constraints, and integrity checks succeed.
        os.replace(temporary, destination)
    finally:
        if temporary.exists():
            temporary.unlink()
    return {"database": str(destination), "tables": counts, "total_rows": sum(counts.values())}


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--data-dir", type=Path, default=ROOT.parent / "data")
    parser.add_argument("--db", type=Path, default=ROOT / "database/retail.db")
    parser.add_argument("--replace", action="store_true", help="Rebuild an existing database")
    args = parser.parse_args()
    try:
        result = build_database(args.data_dir, args.db, replace=args.replace)
    except (OSError, ValueError, sqlite3.Error) as exc:
        parser.exit(1, f"Import failed: {exc}\n")
    print(json.dumps(result, indent=2))


if __name__ == "__main__":
    main()
