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
from .analytics import (
    ANALYTICS_PROMPT,
    AnalyticsPlan,
    AnalyticsResult,
    aggregate,
    grounded_parameters,
)
from .analytics_answer import AnalyticsAnswerer
from .analytics_sql_tool import AnalyticsSqlExecutor, create_analytics_sql_tool
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
        analytics_answer_model: Runnable | None = None,
    ):
        if anchor.utcoffset() is None:
            raise ValueError("Event anchor must include a timezone.")
        self.chain = SQL_PROMPT | model
        self.executor = executor
        self.anchor = anchor.astimezone(timezone(timedelta(hours=5, minutes=30)))
        self.analytics_chain = ANALYTICS_PROMPT | analytics_model if analytics_model else None
        self.analytics_executor = AnalyticsSqlExecutor(
            executor.path, self.anchor, executor.row_limit
        )
        self.policy_agent = None
        self.analytics_answerer = (
            AnalyticsAnswerer(analytics_answer_model)
            if analytics_answer_model is not None
            else None
        )

    def analyze(
        self, question: str, *, authorized_tickets: list[dict], context: dict | None = None
    ) -> AnalyticsResult:
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
            planning_context = {
                key: (context or {}).get(key, {}) for key in ("filters", "time_window")
            }
            for attempt in range(2):
                plan = AnalyticsPlan.model_validate(
                    self.analytics_chain.invoke(
                        {
                            "question": pii.sanitized_text,
                            "context": json.dumps(planning_context),
                        }
                    )
                )
                try:
                    result = self._run_analytics_plan(
                        plan, pii.sanitized_text, authorized_tickets, context or {}
                    )
                    break
                except (SqlValidationError, sqlite3.Error) as exc:
                    if attempt:
                        raise
                    # One correction attempt using schema/error, never results or private rows.
                    planning_context["correction"] = {
                        "previous_sql": plan.sql,
                        "error": str(exc)[:300],
                        "instruction": "Correct the SELECT and all parameter bindings; obey scope.",
                    }
            clean = PIIAgent().sanitize(result.answer)
            if not SafetyAgent().evaluate(clean).allowed:
                raise ValueError("Unsafe planner response")
            result.answer = clean.sanitized_text
            if result.follow_up:
                result.follow_up = result.answer
            result.pii_detected = result.pii_detected or pii.pii_detected
            return result
        except Exception as exc:
            logger.warning("Analytics planning failed (%s)", type(exc).__name__)
            return AnalyticsResult(
                status="unavailable",
                answer="Analytics could not complete that query. Please rephrase or retry.",
                pii_detected=pii.pii_detected,
            )

    def _run_analytics_plan(self, plan, question, tickets, context) -> AnalyticsResult:
        if plan.intent == "retail_query":
            if not plan.sql:
                raise SqlValidationError("The planner omitted SQL")
            tool = create_analytics_sql_tool(self.analytics_executor, tickets, context)
            parameters = {
                **grounded_parameters(question, context, self.executor.row_limit),
                **{
                    binding.name: int(binding.value)
                    if isinstance(binding.value, float) and binding.value.is_integer()
                    else binding.value
                    for binding in plan.parameters
                },
            }
            result = AnalyticsResult.model_validate_json(
                tool.invoke({"sql": plan.sql, "parameters": parameters})
            )
            if self.analytics_answerer is not None:
                return self.analytics_answerer.explain(
                    question, result, sql=plan.sql, parameters=parameters, context=context
                )
            return result
        if plan.intent == "policy":
            if self.policy_agent is None:
                raise RuntimeError("Policy retrieval is not configured")
            policy = self.policy_agent.ask(question)
            return AnalyticsResult(
                status="answer" if policy.status == "answered" else "unavailable",
                intent="policy" if policy.status == "answered" else None,
                answer=policy.answer,
                citations=[
                    {
                        key: getattr(citation, key)
                        for key in ("section_id", "filename", "heading", "source_hash")
                    }
                    for citation in policy.citations
                ],
                limitations=["Policy guidance is grounded in the indexed policy documents."],
            )
        return aggregate(plan, tickets)

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
