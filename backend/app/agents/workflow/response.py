"""Merge policy citations and factual evidence without inventing a synthesis."""

from ..guardrails import PIIAgent, SafetyAgent
from .input import sanitize_text
from .schemas import WorkflowResult, WorkflowState


def compose_result(state: WorkflowState) -> WorkflowResult:
    triage, routing = state.get("triage_result"), state.get("route_decision")
    safety = state.get("safety_result")
    common = {
        "triage": triage,
        "routing": routing,
        "pii_detected": bool(state.get("pii_result") and state["pii_result"].pii_detected),
    }
    if safety and not safety.allowed:
        return WorkflowResult(
            status="refused",
            answer=safety.safe_response,
            human_review_required=True,
            safety_refusal=True,
            **common,
        )
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
        pii = PIIAgent().sanitize(routing.follow_up)
        if not SafetyAgent().evaluate(pii).allowed:
            return WorkflowResult(
                status="unavailable",
                answer="The follow-up failed safety validation. Please seek human review.",
                human_review_required=True,
                **common,
            )
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
    clean = PIIAgent().sanitize(answer)
    if not SafetyAgent().evaluate(clean).allowed:
        return WorkflowResult(
            status="unavailable",
            answer="The generated guidance failed safety validation. Please seek human review.",
            human_review_required=True,
            **common,
        )
    if safety and safety.safe_response:
        answer = safety.safe_response + "\n\n" + answer
    # Sanitize structured evidence and model text as well as the displayed answer.
    if rag:
        rag = rag.model_copy(update={"answer": sanitize_text(rag.answer)})
    if data:
        data = data.model_copy(
            update={
                "summary": sanitize_text(data.summary),
                "evidence": [
                    item.model_copy(
                        update={
                            "rows": [
                                {
                                    key: sanitize_text(value) if isinstance(value, str) else value
                                    for key, value in row.items()
                                }
                                for row in item.rows
                            ]
                        }
                    )
                    for item in data.evidence
                ],
            }
        )
    return WorkflowResult(
        status=status,
        answer=sanitize_text(answer),
        rag=rag,
        data=data,
        human_review_required=triage.priority == "P1"
        or triage.confidence < 0.6
        or status != "answered",
        limitations=[sanitize_text(value) for value in limitations],
        **common,
    )
