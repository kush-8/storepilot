"""Read-only analytics tool over an isolated copy of permitted, pre-scoped data.

The generated query never gets a connection to either original database. Only safe
operational columns and already authorized ticket metadata enter the memory database.
"""

import re
import sqlite3
from contextlib import closing
from datetime import datetime
from pathlib import Path

import sqlglot
from langchain_core.tools import StructuredTool
from pydantic import BaseModel, ConfigDict, Field
from sqlglot import exp

from ..guardrails import PIIAgent
from .analytics import AnalyticsResult
from .sql_tool import SqlValidationError

PUBLIC_COLUMNS = {
    "store_master": "store_id store_name city region pos_registers avg_daily_traffic "
    "nearby_store_id",
    "vendor_master": "vendor_id name on_time_rate fill_rate effective_from status primary_category",
    "product_master": "sku name category vendor_id list_price shelf_life_days storage_type "
    "high_demand warranty_days",
    "inventory": "store_id sku on_hand system_qty reorder_point last_count_date shelf_capacity",
    "receipts": "receipt_id store_id sku vendor_id po_qty received_qty receipt_date "
    "quality_check_ok",
    "returns_quality": "return_id created_ts store_id sku reason refund_amount_inr "
    "receipt_present status",
    "escalation_matrix": "category trigger priority team channel sla_minutes "
    "human_approval_required policy_source",
}
TICKET_COLUMNS = (
    "affected_store_id sku category priority status origin created_at updated_at closed_at"
)
FUNCTIONS = {
    "count",
    "sum",
    "avg",
    "min",
    "max",
    "round",
    "coalesce",
    "nullif",
    "cast",
    "date",
    "datetime",
    "julianday",
    "strftime",
    "abs",
    "lower",
    "upper",
    "length",
    "substr",
    "substring",
    "trim",
    "case",
    "if",
    "like",
    "and",
    "or",
    "not",
    "time_to_str",
    "ts_or_ds_to_timestamp",
    "row_number",
    "rank",
    "dense_rank",
    "lag",
    "lead",
    "first_value",
    "last_value",
}


class AnalyticsSqlInput(BaseModel):
    model_config = ConfigDict(extra="forbid")
    sql: str = Field(min_length=1, max_length=5000)
    parameters: dict[str, str | int | float | None] = Field(default_factory=dict, max_length=20)


def validate(sql: str, parameters: dict) -> tuple[str, set[str]]:
    if ";" in sql.rstrip().rstrip(";") or re.search(r"--|/\*|\*/", sql):
        raise SqlValidationError("Only one uncommented SELECT is allowed.")
    try:
        statements = sqlglot.parse(sql, read="sqlite")
    except sqlglot.errors.ParseError as exc:
        raise SqlValidationError("Invalid SQL.") from exc
    if len(statements) != 1 or not isinstance(statements[0], exp.Query):
        raise SqlValidationError("Only SELECT queries are allowed.")
    tree = statements[0]
    if any(
        isinstance(
            node,
            (
                exp.Insert,
                exp.Update,
                exp.Delete,
                exp.Create,
                exp.Drop,
                exp.Alter,
                exp.Command,
                exp.Attach,
                exp.Transaction,
            ),
        )
        for node in tree.walk()
    ):
        raise SqlValidationError("Only read-only queries are allowed.")
    if any(
        isinstance(node, exp.Star) and not isinstance(node.parent, exp.Count)
        for node in tree.walk()
    ):
        raise SqlValidationError("Select explicit columns.")
    references = list(tree.find_all(exp.Table))
    if any(table.db or table.catalog for table in references):
        raise SqlValidationError("Qualified tables are not allowed.")
    ctes = {cte.alias.lower() for cte in tree.find_all(exp.CTE)}
    tables = {table.name.lower() for table in references} - ctes
    if not tables or not tables <= (set(PUBLIC_COLUMNS) | {"visible_tickets"}):
        raise SqlValidationError("Query references restricted tables.")
    functions = {
        function.name.lower()
        if isinstance(function, exp.Anonymous)
        else function.sql_name().lower()
        for function in tree.find_all(exp.Func)
    }
    if functions - FUNCTIONS:
        raise SqlValidationError("Unsupported SQL function.")
    placeholders = {node.name for node in tree.find_all(exp.Placeholder)}
    if any(not re.fullmatch(r"[a-zA-Z][a-zA-Z0-9_]{0,39}", name) for name in parameters):
        raise SqlValidationError("Invalid parameter name.")
    if placeholders - parameters.keys():
        raise SqlValidationError("Missing SQL parameters.")
    return tree.sql(dialect="sqlite"), tables


class AnalyticsSqlExecutor:
    def __init__(self, path: Path, anchor: datetime, row_limit: int = 50):
        if not 1 <= row_limit <= 100:
            raise ValueError("row_limit must be 1 to 100.")
        self.path, self.anchor, self.row_limit = path, anchor, row_limit

    def _populate(self, db, tickets, context, tables):
        filters = context.get("filters", {})
        window = context.get("time_window", {})
        end = (
            min(datetime.fromisoformat(window["end"]), self.anchor)
            if window.get("end")
            else self.anchor
        )
        start = datetime.fromisoformat(window["start"]) if window.get("start") else None
        end = end.astimezone(self.anchor.tzinfo)
        start = start.astimezone(self.anchor.tzinfo) if start else None
        source_tables = tables - {"visible_tickets"}
        if source_tables:
            with closing(
                sqlite3.connect(self.path.resolve().as_uri() + "?mode=ro", uri=True)
            ) as src:
                for table in sorted(source_tables):
                    columns = PUBLIC_COLUMNS[table].split()
                    types = {row[1]: row[2] for row in src.execute(f"PRAGMA table_info({table})")}
                    definitions = ",".join(f'"{c}" {types[c]}' for c in columns)
                    db.execute(f'CREATE TABLE "{table}" ({definitions})')
                    where, values = [], []
                    for key in ("store_id", "sku"):
                        if filters.get(key) and key in columns:
                            where.append(f"{key}=?")
                            values.append(filters[key])
                    if table in {"receipts", "returns_quality"}:
                        column = "receipt_date" if table == "receipts" else "created_ts"

                        def boundary(value):
                            return (
                                value.date().isoformat()
                                if table == "receipts"
                                else value.strftime("%Y-%m-%d %H:%M:%S")
                            )

                        where.append(f"{column}<=?")
                        values.append(boundary(end))
                        if start:
                            where.append(f"{column}>?")
                            values.append(boundary(start))
                    query = f'SELECT {",".join(columns)} FROM "{table}"'
                    if where:
                        query += " WHERE " + " AND ".join(where)
                    rows = src.execute(query, values)
                    marks = ",".join("?" for _ in columns)
                    db.executemany(f'INSERT INTO "{table}" VALUES ({marks})', rows)
        if "visible_tickets" in tables:
            columns = TICKET_COLUMNS.split()

            def ticket_value(ticket, column):
                value = ticket.get(column)
                if value and column.endswith("_at"):
                    timestamp = datetime.fromisoformat(value)
                    if timestamp.tzinfo is None:
                        raise ValueError("Ticket timestamps require a timezone")
                    return timestamp.astimezone(self.anchor.tzinfo).strftime("%Y-%m-%d %H:%M:%S")
                return value

            db.execute(
                "CREATE TABLE visible_tickets (" + ",".join(f"{c} TEXT" for c in columns) + ")"
            )
            db.executemany(
                "INSERT INTO visible_tickets VALUES (" + ",".join("?" for _ in columns) + ")",
                [tuple(ticket_value(ticket, c) for c in columns) for ticket in tickets],
            )

    def execute(
        self, sql: str, parameters: dict, *, authorized_tickets: list[dict], context: dict
    ) -> AnalyticsResult:
        normalized, tables = validate(sql, parameters)
        with closing(sqlite3.connect(":memory:")) as db:
            db.row_factory = sqlite3.Row
            self._populate(db, authorized_tickets, context, tables)
            coverage = {}
            for table in sorted(tables):
                columns = (
                    TICKET_COLUMNS if table == "visible_tickets" else PUBLIC_COLUMNS[table]
                ).split()
                where, values = [], []
                for key in ("store_id", "sku", "vendor_id"):
                    column = (
                        "affected_store_id"
                        if table == "visible_tickets" and key == "store_id"
                        else key
                    )
                    if parameters.get(key) is not None and column in columns:
                        where.append(f"{column}=?")
                        values.append(parameters[key])
                query = f'SELECT COUNT(*) FROM "{table}"'
                if where:
                    query += " WHERE " + " AND ".join(where)
                coverage[table] = db.execute(query, values).fetchone()[0]
            db.execute("PRAGMA query_only=ON")
            budget = 0

            def bounded():
                nonlocal budget
                budget += 1
                return int(budget > 1000)

            db.set_progress_handler(bounded, 1000)
            cursor = db.execute(
                f"SELECT * FROM ({normalized}) AS analytics_result LIMIT :__cap",
                {**parameters, "__cap": self.row_limit + 1},
            )
            keys = [column[0] for column in cursor.description]
            if len(keys) != len(set(keys)) or any(not 1 <= len(key) <= 100 for key in keys):
                raise SqlValidationError("Select unique, concise column aliases.")
            raw = [dict(row) for row in cursor]
        truncated = len(raw) > self.row_limit
        rows = [
            {
                key: PIIAgent().sanitize(value[:2000]).sanitized_text
                if isinstance(value, str)
                else value
                for key, value in row.items()
            }
            for row in raw[: self.row_limit]
        ]
        columns = [
            {
                "key": key,
                "label": key.replace("_", " ").title(),
                "value_type": "number"
                if any(isinstance(row[key], (int, float)) for row in rows)
                else "string",
            }
            for key in keys
        ]
        if not rows:
            answer = "No matching records were found within the selected filters."
        elif len(rows) == 1:
            answer = "; ".join(f"{column['label']}: {rows[0][column['key']]}" for column in columns)
        else:
            answer = f"Found {len(rows)} result rows" + (
                " (more results available)." if truncated else "."
            )
        limitations = [
            "Queries are read-only. Ticket results use selected filters and "
            "current employee levels.",
            "Stock, products, vendors, deliveries and returns come from the retail snapshot; "
            "they are not live feeds. Delivery dates have day precision.",
        ]
        if truncated:
            limitations.append(
                f"Showing the first {self.row_limit} rows. Narrow the question or filters."
            )
        return AnalyticsResult(
            status="answer",
            source_row_counts=coverage,
            intent="retail_query",
            answer=answer[:12000],
            columns=columns,
            rows=rows,
            truncated=truncated,
            limitations=limitations,
            query_template_ids=["validated_retail_analytics"],
            evidence=[
                {
                    "source": ", ".join(sorted(tables))[:100],
                    "record_ids": [],
                    "summary": f"Read-only query returned {len(rows)} row(s).",
                    "query_template_id": "validated_retail_analytics",
                }
            ],
        )


def create_analytics_sql_tool(executor: AnalyticsSqlExecutor, tickets: list[dict], context: dict):
    def execute(sql: str, parameters: dict | None = None) -> str:
        """Execute a validated SQLite SELECT against permitted, caller-scoped analytics data."""
        return executor.execute(
            sql, parameters or {}, authorized_tickets=tickets, context=context
        ).model_dump_json()

    return StructuredTool.from_function(
        func=execute, name="execute_analytics_sql", args_schema=AnalyticsSqlInput
    )
