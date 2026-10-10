"""Merge policy citations and factual evidence without inventing a synthesis."""

from .input import sanitize_text
from .schemas import WorkflowResult, WorkflowState


def compose_result(state: WorkflowState) -> WorkflowResult:
    triage, routing = state.get("triage_result"), state.get("route_decision")
    common = {"triage": triage, "routing": routing}
    if state.get("error"):
        return WorkflowResult(
            status="unavailable", answer=state["error"], human_review_required=True, **common
        )
    if routing.route == "refuse":
        return WorkflowResult(
            status="refused",
            answer="I can help with supported retail policy "
            "and authorized operational questions, but cannot fulfill this request.",
            human_review_required=triage.restricted_request,
            **common,
        )
    if routing.route == "clarify":
        return WorkflowResult(
            status="needs_clarification",
            answer=sanitize_text(routing.follow_up),
            human_review_required=triage.confidence < 0.6,
            **common,
        )
    rag, data = state.get("rag_result"), state.get("data_result")
    outputs = [part for part in (rag, data) if part is not None]
    successes = sum(part.status == "answered" for part in outputs)
    limitations = []
    if rag and rag.status != "answered":
        limitations.append("Policy guidance could not be fully established.")
    if data and data.status != "answered":
        limitations.append(data.summary)
    if data and any(item.truncated for item in data.evidence):
        limitations.append("Data results are capped; returned rows are not complete totals.")
    if successes == len(outputs) and outputs:
        status = "answered"
    elif successes:
        status = "partial"
    elif data and data.status == "needs_clarification":
        status = "needs_clarification"
    elif (rag and rag.status in {"model_unavailable", "invalid_response"}) or (
        data and data.status in {"unavailable", "forbidden", "invalid_query", "model_unavailable"}
    ):
        status = "unavailable"
    else:
        status = "insufficient_evidence"
    answer = "\n\n".join(
        part
        for part in (
            f"Policy guidance:\n{rag.answer}" if rag else None,
            f"Operational data:\n{data.summary}" if data else None,
        )
        if part
    )
    return WorkflowResult(
        status=status,
        answer=sanitize_text(answer),
        rag=rag,
        data=data,
        human_review_required=triage.priority == "P1"
        or triage.confidence < 0.6
        or status != "answered",
        limitations=limitations,
        **common,
    )
