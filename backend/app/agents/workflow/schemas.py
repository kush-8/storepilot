from typing import Literal, NotRequired, TypedDict

from pydantic import BaseModel, Field

from ..data.schemas import DataResult
from ..guardrails import PIIResult, SafetyResult
from ..rag.schemas import RagResult
from ..router.schemas import RouteDecision
from ..triage.schemas import TriageResult


class WorkflowResult(BaseModel):
    status: Literal[
        "answered",
        "partial",
        "needs_clarification",
        "refused",
        "unavailable",
        "insufficient_evidence",
    ]
    answer: str
    triage: TriageResult | None = None
    routing: RouteDecision | None = None
    rag: RagResult | None = None
    data: DataResult | None = None
    human_review_required: bool = False
    limitations: list[str] = Field(default_factory=list)
    pii_detected: bool = False
    safety_refusal: bool = False


class WorkflowInput(TypedDict):
    question: str
    viewer_employee_id: str | None
    entity_context: NotRequired[dict[str, str]]


class WorkflowState(WorkflowInput, total=False):
    triage_result: TriageResult
    route_decision: RouteDecision
    rag_result: RagResult
    data_result: DataResult
    error: str
    pii_result: PIIResult
    safety_result: SafetyResult
    result: WorkflowResult


class WorkflowOutput(TypedDict):
    result: WorkflowResult
