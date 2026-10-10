"""Model-generated SQL planning followed by a validated LangChain SQL tool."""

import json
import logging
import sqlite3
from datetime import datetime, timedelta, timezone

from langchain_core.runnables import Runnable, RunnableConfig
from pydantic import ValidationError

from ..guardrails import PIIAgent, SafetyAgent
from ..router.schemas import RouteDecision
from ..triage.schemas import TriageResult
from .analytics import ANALYTICS_PROMPT, AnalyticsPlan, AnalyticsResult, aggregate
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
    def __init__(
        self,
        model: Runnable,
        executor: ReadOnlySqlExecutor,
        anchor: datetime,
        analytics_model: Runnable | None = None,
    ):
        if anchor.utcoffset() is None:
            raise ValueError("Event anchor must include a timezone.")
        self.chain = SQL_PROMPT | model
        self.executor = executor
        self.anchor = anchor.astimezone(timezone(timedelta(hours=5, minutes=30)))
        self.analytics_chain = ANALYTICS_PROMPT | analytics_model if analytics_model else None

    def analyze(self, question: str, *, authorized_tickets: list[dict]) -> AnalyticsResult:
        """Caller supplies rows already scoped using current directory levels and dates.

        Only the sanitized question reaches the model; aggregation never sends ticket
        titles, descriptions, creator IDs or hidden rows to an external provider.
        """
        pii = PIIAgent().sanitize(question)
        safety = SafetyAgent().evaluate(pii)
        if not safety.allowed:
            return AnalyticsResult(
                status="refusal",
                answer=safety.safe_response,
                pii_detected=pii.pii_detected,
                safety_refusal=True,
            )
        try:
            if self.analytics_chain is None:
                raise RuntimeError("Analytics planner is not configured")
            plan = AnalyticsPlan.model_validate(
                self.analytics_chain.invoke({"question": pii.sanitized_text})
            )
            result = aggregate(plan, authorized_tickets)
            clean = PIIAgent().sanitize(result.answer)
            if not SafetyAgent().evaluate(clean).allowed:
                raise ValueError("Unsafe planner response")
            result.answer = clean.sanitized_text
            if result.follow_up:
                result.follow_up = result.answer
            result.pii_detected = pii.pii_detected
            return result
        except Exception as exc:
            logger.warning("Analytics planning failed (%s)", type(exc).__name__)
            return AnalyticsResult(
                status="unavailable",
                answer="Ticket analytics is unavailable. Please retry.",
                pii_detected=pii.pii_detected,
            )

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
        if not self.executor.path.is_file():
            return DataResult(status="unavailable", summary="The retail database is unavailable.")
        if "inventory" in plan.queries and not (triage.entities.store_id or triage.entities.sku):
            return DataResult(status="needs_clarification", summary="Provide a store or SKU.")
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
