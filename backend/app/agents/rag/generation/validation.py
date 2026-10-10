"""Deterministic citation checks; never trust model-generated source metadata."""

from ...guardrails import PIIAgent, SafetyAgent
from ..schemas import GeneratedAnswer, RagResult, RetrievedSection

ABSTENTION = "I cannot confirm this from the available policy documents. Please seek human review."


def abstention(sections: list[RetrievedSection]) -> RagResult:
    return RagResult(status="insufficient_evidence", answer=ABSTENTION, retrieved_sections=sections)


def validate_answer(draft: GeneratedAnswer, sections: list[RetrievedSection]) -> RagResult:
    if draft.insufficient_evidence or not draft.statements:
        return abstention(sections)
    available = {item.section_id: item for item in sections}
    if any(
        not SafetyAgent().evaluate(PIIAgent().sanitize(statement.text)).allowed
        for statement in draft.statements
    ):
        return RagResult(
            status="invalid_response",
            answer="Generated advice failed safety validation. Please seek human review.",
        )
    cited = list(
        dict.fromkeys(ref for statement in draft.statements for ref in statement.citation_ids)
    )
    if any(ref not in available for ref in cited) or any(
        not statement.text.strip() for statement in draft.statements
    ):
        return RagResult(
            status="invalid_response",
            answer="The answer contained invalid policy citations. Please seek human review.",
            retrieved_sections=sections,
        )
    answer = "\n".join(
        PIIAgent().sanitize(statement.text.strip()).sanitized_text
        + " "
        + " ".join(f"[{ref}]" for ref in dict.fromkeys(statement.citation_ids))
        for statement in draft.statements
    )
    return RagResult(
        status="answered",
        answer=answer,
        citations=[available[ref] for ref in cited],
        retrieved_sections=sections,
    )
