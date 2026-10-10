"""Local minimization before graph/model input; no raw input is checkpointed."""

from ..guardrails import PIIAgent


def sanitize_text(text: str) -> str:
    return PIIAgent().sanitize(text).sanitized_text


def prepare_question(question: str) -> str:
    if not isinstance(question, str) or not question.strip() or len(question) > 4000:
        raise ValueError("Question must contain 1 to 4000 characters.")
    return sanitize_text(question.strip())
