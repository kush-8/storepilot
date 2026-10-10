"""Read-only database health and dashboard endpoints for the React scaffold."""

from __future__ import annotations

import os
import sqlite3
from contextlib import contextmanager
from pathlib import Path

from dotenv import load_dotenv
from fastapi import FastAPI, HTTPException
from pydantic import BaseModel

BACKEND_ROOT = Path(__file__).resolve().parents[1]
load_dotenv(BACKEND_ROOT / ".env")
ANCHOR = "2026-10-10T12:00:00+05:30"
TABLES = (
    "store_master", "vendor_master", "product_master", "employee_master",
    "inventory", "receipts", "returns_quality", "support_cases", "escalation_matrix",
)
app = FastAPI(title="Punjab Sports Mart Copilot", version="0.1.0")


class Health(BaseModel):
    status: str
    database_ready: bool
    business_tables: int
    total_rows: int
    anchor_timestamp: str


class Distribution(BaseModel):
    name: str
    count: int


class Dashboard(BaseModel):
    anchor_timestamp: str
    total_cases: int
    unresolved_cases: int
    unresolved_p1: int
    unresolved_p2: int
    priority_distribution: list[Distribution]
    category_distribution: list[Distribution]
    region_distribution: list[Distribution]


@contextmanager
def database():
    configured = Path(os.getenv("DATABASE_PATH", "database/retail.db"))
    path = configured if configured.is_absolute() else BACKEND_ROOT / configured
    try:
        connection = sqlite3.connect(path.resolve().as_uri() + "?mode=ro", uri=True)
        connection.row_factory = sqlite3.Row
        try:
            yield connection
        finally:
            connection.close()
    except sqlite3.Error as exc:
        raise HTTPException(status_code=503, detail="Retail database is unavailable or invalid") from exc


@app.get("/api/health", response_model=Health)
def health() -> Health:
    with database() as connection:
        total = sum(
            connection.execute(f'SELECT COUNT(*) FROM "{table}"').fetchone()[0]
            for table in TABLES
        )
        return Health(
            status="ok", database_ready=True, business_tables=len(TABLES),
            total_rows=total, anchor_timestamp=ANCHOR,
        )


@app.get("/api/dashboard", response_model=Dashboard)
def dashboard() -> Dashboard:
    with database() as connection:
        # Aggregate historical cases at the fixed event anchor, excluding future records.
        cutoff = "2026-10-10 12:00:00"
        summary = connection.execute(
            """SELECT COUNT(*) AS total_cases,
               SUM(CASE WHEN status IN ('Open', 'In Progress') THEN 1 ELSE 0 END) AS unresolved,
               SUM(CASE WHEN status IN ('Open', 'In Progress') AND priority_label = 'P1'
                   THEN 1 ELSE 0 END) AS p1,
               SUM(CASE WHEN status IN ('Open', 'In Progress') AND priority_label = 'P2'
                   THEN 1 ELSE 0 END) AS p2
               FROM support_cases WHERE created_ts <= ?""", (cutoff,),
        ).fetchone()

        def distribution(sql: str) -> list[Distribution]:
            return [Distribution(name=row[0], count=row[1])
                    for row in connection.execute(sql, (cutoff,))]

        return Dashboard(
            anchor_timestamp=ANCHOR,
            total_cases=summary["total_cases"], unresolved_cases=summary["unresolved"] or 0,
            unresolved_p1=summary["p1"] or 0, unresolved_p2=summary["p2"] or 0,
            priority_distribution=distribution(
                "SELECT priority_label, COUNT(*) FROM support_cases "
                "WHERE status IN ('Open', 'In Progress') AND created_ts <= ? "
                "GROUP BY priority_label ORDER BY priority_label"
            ),
            category_distribution=distribution(
                "SELECT category_label, COUNT(*) FROM support_cases "
                "WHERE status IN ('Open', 'In Progress') AND created_ts <= ? "
                "GROUP BY category_label ORDER BY COUNT(*) DESC, category_label"
            ),
            region_distribution=distribution(
                "SELECT s.region, COUNT(*) FROM support_cases c "
                "JOIN store_master s ON c.store_id = s.store_id "
                "WHERE c.status IN ('Open', 'In Progress') AND c.created_ts <= ? "
                "GROUP BY s.region ORDER BY COUNT(*) DESC, s.region"
            ),
        )
