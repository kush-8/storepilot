"""Immutable operational sources and transactional, separately persisted application state."""

import json
import os
import sqlite3
from contextlib import contextmanager
from datetime import datetime, timezone
from pathlib import Path
from uuid import uuid4

from dotenv import load_dotenv
from fastapi import HTTPException

ROOT = Path(__file__).resolve().parents[1]
load_dotenv(ROOT / ".env")
ANCHOR = datetime.fromisoformat("2026-10-10T12:00:00+05:30")


def now():
    return datetime.now(timezone.utc)


def uid():
    return str(uuid4())


def fail(status, message):
    raise HTTPException(status, message)


def path_for(setting, default):
    path = Path(os.getenv(setting, default))
    return path if path.is_absolute() else ROOT / path


@contextmanager
def source():
    try:
        db = sqlite3.connect(
            path_for("DATABASE_PATH", "database/retail.db").resolve().as_uri() + "?mode=ro",
            uri=True,
        )
        db.row_factory = sqlite3.Row
        try:
            yield db
        finally:
            db.close()
    except sqlite3.Error as exc:
        raise HTTPException(503, "Retail database is unavailable") from exc


@contextmanager
def state():
    path = path_for("APPLICATION_DATABASE_PATH", "database/storepilot.db")
    if path.resolve() == path_for("DATABASE_PATH", "database/retail.db").resolve():
        fail(503, "Application database must be separate from source database")
    try:
        db = sqlite3.connect(path, timeout=15)
        db.row_factory = sqlite3.Row
        db.execute("PRAGMA foreign_keys=ON")
        db.executescript("""
            CREATE TABLE IF NOT EXISTS sessions (
                digest TEXT PRIMARY KEY, employee TEXT NOT NULL, store TEXT NOT NULL,
                expires REAL NOT NULL, revoked INTEGER NOT NULL DEFAULT 0);
            CREATE TABLE IF NOT EXISTS records (
                kind TEXT NOT NULL, id TEXT NOT NULL, owner TEXT NOT NULL, payload TEXT NOT NULL,
                PRIMARY KEY(kind,id));
            CREATE TABLE IF NOT EXISTS receipts (
                owner TEXT NOT NULL, key TEXT NOT NULL, digest TEXT NOT NULL,
                ticket_id TEXT NOT NULL, draft_id TEXT NOT NULL UNIQUE, PRIMARY KEY(owner,key));
            CREATE TABLE IF NOT EXISTS turns (
                conversation_id TEXT NOT NULL, client_id TEXT NOT NULL, digest TEXT NOT NULL,
                payload TEXT NOT NULL, PRIMARY KEY(conversation_id,client_id));
            CREATE TABLE IF NOT EXISTS rate_limits (
                key TEXT PRIMARY KEY, starts REAL NOT NULL, count INTEGER NOT NULL);
            PRAGMA user_version=1;
        """)
        db.execute("BEGIN IMMEDIATE")
        try:
            yield db
            db.commit()
        except BaseException:
            db.rollback()
            raise
        finally:
            db.close()
    except sqlite3.Error as exc:
        raise HTTPException(503, "Application database is unavailable") from exc


def get_record(db, kind, key, owner=None):
    row = db.execute(
        "SELECT owner,payload FROM records WHERE kind=? AND id=?", (kind, str(key))
    ).fetchone()
    if not row or (owner is not None and row["owner"] != owner):
        fail(404, "Resource not found")
    return json.loads(row["payload"])


def put_record(db, kind, key, owner, data):
    db.execute(
        "INSERT INTO records VALUES (?,?,?,?) ON CONFLICT(kind,id) "
        "DO UPDATE SET payload=excluded.payload",
        (kind, str(key), owner, json.dumps(data)),
    )


def directory():
    with source() as db:
        return {r["employee_id"]: dict(r) for r in db.execute("SELECT * FROM employee_master")}


def employee_context(row):
    return dict(
        employee_id=row["employee_id"],
        assigned_store_id=row["store_id"],
        role=row["role"],
        escalation_level=row["escalation_level"],
    )


def check_reference(store=None, sku=None):
    with source() as db:
        for table, column, value in [
            ("store_master", "store_id", store),
            ("product_master", "sku", sku),
        ]:
            if (
                value
                and not db.execute(f"SELECT 1 FROM {table} WHERE {column}=?", (value,)).fetchone()
            ):
                fail(422, "Unknown store or SKU")
