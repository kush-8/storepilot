"""Model-generated SQL planning followed by a validated LangChain SQL tool."""

import json
import logging
import sqlite3
from datetime import datetime, timedelta, timezone

from langchain_core.runnables import Runnable, RunnableConfig
from pydantic import ValidationError

from ..router.schemas import RouteDecision
from ..triage.schemas import TriageResult
from .prompts import SQL_PROMPT, SQL_SCHEMA
from .schemas import DataEvidence, DataResult, GeneratedSqlPlan
from .sql_tool import (
    DataAccessDenied,
    ReadOnlySqlExecutor,
    SqlValidationError,
    create_sql_query_tool,
)

logger = logging.getLogger(__name__)


class DataAgent:
    def __init__(self, model: Runnable, executor: ReadOnlySqlExecutor, anchor: datetime):
        if anchor.utcoffset() is None:
            raise ValueError("Event anchor must include a timezone.")
        self.chain = SQL_PROMPT | model
        self.executor = executor
        self.anchor = anchor.astimezone(timezone(timedelta(hours=5, minutes=30)))

    def _parameters(self, triage: TriageResult, plan: RouteDecision) -> dict:
        start = self.anchor - timedelta(days=plan.lookback_days)
        return {
            **triage.entities.model_dump(),
            "start": start.strftime("%Y-%m-%d %H:%M:%S"),
            "end": self.anchor.strftime("%Y-%m-%d %H:%M:%S"),
            "start_date": start.date().isoformat(),
            "end_date": self.anchor.date().isoformat(),
            "limit": self.executor.row_limit,
        }

    def invoke(
        self,
        question: str,
        plan: RouteDecision,
        triage: TriageResult,
        viewer_employee_id: str | None = None,
        config: RunnableConfig | None = None,
    ) -> DataResult:
        parameters = self._parameters(triage, plan)
        try:
            generated = GeneratedSqlPlan.model_validate(
                self.chain.invoke(
                    {
                        "schema": SQL_SCHEMA,
                        "question": question,
                        "evidence_types": json.dumps(plan.queries),
                        "entities": triage.entities.model_dump_json(),
                        "time_parameters": json.dumps(
                            {
                                key: parameters[key]
                                for key in ("start", "end", "start_date", "end_date", "limit")
                            }
                        ),
                    },
                    config=config,
                )
            )
        except (ValidationError, Exception) as exc:
            logger.warning("SQL generation failed (%s)", type(exc).__name__)
            return DataResult(
                status="model_unavailable", summary="The SQL planning model is unavailable."
            )
        if [query.evidence_type for query in generated.queries] != list(plan.queries):
            return DataResult(
                status="invalid_query",
                summary="The generated SQL plan did not match the router's evidence plan.",
            )
        tool = create_sql_query_tool(self.executor, parameters, viewer_employee_id)
        evidence: list[DataEvidence] = []
        try:
            for query in generated.queries:
                payload = tool.invoke(query.model_dump(), config=config)
                evidence.append(DataEvidence.model_validate_json(payload))
        except DataAccessDenied:
            return DataResult(
                status="forbidden", summary="Case data requires verified employee context."
            )
        except SqlValidationError:
            return DataResult(
                status="invalid_query", summary="The generated SQL did not pass validation."
            )
        except sqlite3.Error:
            return DataResult(status="unavailable", summary="The retail database is unavailable.")
        if not any(item.rows for item in evidence):
            return DataResult(
                status="no_data",
                summary="No matching records in the retail snapshot. "
                "Missing data does not establish zero stock or availability.",
                evidence=evidence,
            )
        lines = ["Retail snapshot evidence (not live availability):"]
        for item in evidence:
            lines.append(f"{item.query}: {len(item.rows)} result row(s) [{item.evidence_id}].")
            lines.extend(json.dumps(row, ensure_ascii=True) for row in item.rows[:3])
            if item.truncated or len(item.rows) > 3:
                lines.append("Preview only; inspect structured evidence for details and limits.")
            if item.window_start:
                lines.append(f"Window: ({item.window_start}, {item.window_end}].")
            if item.query == "receipts":
                lines.append("Receipt dates have day precision; boundaries use calendar dates.")
        return DataResult(status="answered", summary="\n".join(lines), evidence=evidence)
