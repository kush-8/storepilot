"""Validated read-only SQLite execution exposed as a LangChain SQL tool."""

import re
import sqlite3
from contextlib import closing
from pathlib import Path

import sqlglot
from langchain_core.tools import StructuredTool
from pydantic import BaseModel, ConfigDict, Field
from sqlglot import exp

from ..router.schemas import QueryName
from .schemas import DataEvidence

TABLES_BY_EVIDENCE: dict[QueryName, set[str]] = {
    "inventory": {"inventory", "product_master", "store_master"},
    "product": {"product_master", "vendor_master"},
    "store": {"store_master"},
    "receipts": {"receipts", "product_master", "vendor_master", "store_master"},
    "vendor": {"vendor_master", "product_master"},
    "returns": {"returns_quality", "product_master", "store_master"},
    "case_summary": {"visible_support_cases"},
}
FORBIDDEN_COLUMNS = {
    "employee_id",
    "employee_name",
    "issue_text",
    "root_cause_hint",
    "damage_notes",
    "notes",
    "source_sha256",
    "imported_at_utc",
}
ALLOWED_FUNCTIONS = {"count", "sum", "avg", "min", "max", "round", "coalesce", "nullif"}
ALLOWED_PARAMETERS = {
    "store_id",
    "sku",
    "vendor_id",
    "start",
    "end",
    "start_date",
    "end_date",
    "limit",
}


class SqlToolInput(BaseModel):
    model_config = ConfigDict(extra="forbid")
    evidence_type: QueryName
    sql: str = Field(min_length=1, max_length=5000)


class SqlValidationError(ValueError):
    pass


class DataAccessDenied(PermissionError):
    pass


class ReadOnlySqlExecutor:
    def __init__(self, path: Path, row_limit: int = 50):
        if not 1 <= row_limit <= 100:
            raise ValueError("row_limit must be 1 to 100.")
        self.path, self.row_limit = path, row_limit

    def _validate(self, sql: str, evidence_type: QueryName, parameters: dict) -> str:
        if ";" in sql.rstrip().rstrip(";") or re.search(r"--|/\*|\*/", sql):
            raise SqlValidationError("SQL must be one uncommented statement.")
        try:
            statements = sqlglot.parse(sql, read="sqlite")
        except sqlglot.errors.ParseError as exc:
            raise SqlValidationError("SQL could not be parsed.") from exc
        if len(statements) != 1 or not isinstance(statements[0], exp.Query):
            raise SqlValidationError("Only one SELECT query is allowed.")
        tree = statements[0]
        forbidden_nodes = (
            exp.Insert,
            exp.Update,
            exp.Delete,
            exp.Create,
            exp.Drop,
            exp.Alter,
            exp.Command,
            exp.Attach,
            exp.Transaction,
        )
        if any(isinstance(node, forbidden_nodes) for node in tree.walk()):
            raise SqlValidationError("Only read-only SELECT queries are allowed.")
        if any(isinstance(node, exp.Star) for node in tree.walk()):
            raise SqlValidationError("SELECT * is not allowed.")
        tables = {table.name.lower() for table in tree.find_all(exp.Table)}
        if not tables or not tables <= TABLES_BY_EVIDENCE[evidence_type]:
            raise SqlValidationError("Query references a table outside its evidence scope.")
        columns = {column.name.lower() for column in tree.find_all(exp.Column)}
        if columns & FORBIDDEN_COLUMNS:
            raise SqlValidationError("Query references restricted columns.")
        if any(literal.is_string for literal in tree.find_all(exp.Literal)):
            raise SqlValidationError("String literals are not allowed; use named parameters.")
        functions = {
            function.sql_name().lower()
            for function in tree.find_all(exp.Func)
            if function.sql_name().lower() not in {"cast"}
        }
        if functions - ALLOWED_FUNCTIONS:
            raise SqlValidationError("Query uses an unsupported SQL function.")
        placeholders = {placeholder.name for placeholder in tree.find_all(exp.Placeholder)}
        if placeholders - ALLOWED_PARAMETERS:
            raise SqlValidationError("Query uses an unsupported parameter.")
        if any(parameters.get(name) is None for name in placeholders):
            raise SqlValidationError("Query uses a parameter with no grounded value.")
        if evidence_type == "case_summary":
            non_aggregate = [
                expression
                for expression in tree.expressions
                if not isinstance(expression, (exp.Alias, exp.AggFunc))
            ]
            # GROUP BY dimensions are safe; the view itself contains no text or identities.
            if not any(tree.find_all(exp.AggFunc)):
                raise SqlValidationError("Case queries must aggregate authorized rows.")
            if non_aggregate and not tree.args.get("group"):
                raise SqlValidationError("Case detail rows are not allowed.")
        return tree.sql(dialect="sqlite")

    def execute(
        self,
        evidence_type: QueryName,
        sql: str,
        parameters: dict,
        viewer_employee_id: str | None,
    ) -> DataEvidence:
        normalized = self._validate(sql, evidence_type, parameters)
        with closing(sqlite3.connect(self.path.resolve().as_uri() + "?mode=ro", uri=True)) as conn:
            conn.row_factory = sqlite3.Row
            if evidence_type == "case_summary":
                if (
                    not viewer_employee_id
                    or not conn.execute(
                        "SELECT 1 FROM employee_master WHERE employee_id=?",
                        (viewer_employee_id,),
                    ).fetchone()
                ):
                    raise DataAccessDenied("Case data requires verified employee context.")
                quoted = conn.execute("SELECT quote(?)", (viewer_employee_id,)).fetchone()[0]
                conn.execute(f"""CREATE TEMP VIEW visible_support_cases AS
                    SELECT c.created_ts, c.store_id, c.sku, c.category_label,
                           c.priority_label, c.status
                    FROM support_cases c
                    JOIN employee_master creator ON creator.employee_id=c.employee_id
                    JOIN employee_master viewer ON viewer.employee_id={quoted}
                    WHERE creator.escalation_level <= viewer.escalation_level""")
            conn.execute("PRAGMA query_only=ON")
            wrapped = f"SELECT * FROM ({normalized}) AS generated_query LIMIT :__tool_limit"
            bound = {**parameters, "__tool_limit": self.row_limit + 1}
            rows = [dict(row) for row in conn.execute(wrapped, bound)]
        truncated = len(rows) > self.row_limit
        temporal = evidence_type in {"receipts", "returns", "case_summary"}
        date_only = evidence_type == "receipts"
        return DataEvidence(
            evidence_id=f"retail:generated-sql:{evidence_type}",
            query=evidence_type,
            rows=rows[: self.row_limit],
            truncated=truncated,
            window_start=parameters["start_date" if date_only else "start"] if temporal else None,
            window_end=parameters["end_date" if date_only else "end"] if temporal else None,
            sql=normalized,
        )


def create_sql_query_tool(
    executor: ReadOnlySqlExecutor,
    parameters: dict,
    viewer_employee_id: str | None,
) -> StructuredTool:
    def execute_sql(evidence_type: QueryName, sql: str) -> str:
        """Execute one validated, parameterized, read-only SQLite SELECT query."""
        evidence = executor.execute(evidence_type, sql, parameters, viewer_employee_id)
        return evidence.model_dump_json()

    return StructuredTool.from_function(
        func=execute_sql,
        name="execute_retail_sql",
        description="Validate and execute one read-only SQLite SELECT against retail data.",
        args_schema=SqlToolInput,
    )
