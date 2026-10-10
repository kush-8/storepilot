from typing import Literal, TypedDict

from pydantic import BaseModel, Field

from ..data.schemas import DataResult
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


class WorkflowInput(TypedDict):
    question: str
    viewer_employee_id: str | None


class WorkflowState(WorkflowInput, total=False):
    triage_result: TriageResult
    route_decision: RouteDecision
    rag_result: RagResult
    data_result: DataResult
    error: str
    result: WorkflowResult


class WorkflowOutput(TypedDict):
    result: WorkflowResult
