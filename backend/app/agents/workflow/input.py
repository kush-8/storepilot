"""Local minimization before graph/model input; no raw input is checkpointed."""

import re


def sanitize_text(text: str) -> str:
    text = re.sub(r"\b[A-Za-z0-9._%+-]+@[A-Za-z0-9.-]+\.[A-Za-z]{2,}\b", "[EMAIL]", text)
    text = re.sub(r"\b(?:gsk_|sk-)[A-Za-z0-9_-]+", "[SECRET]", text)
    text = re.sub(r"(?<![\w.])\+?(?:\d[ -]?){9,18}\d(?![\w.])", "[PRIVATE_NUMBER]", text)
    return re.sub(
        r"(?i)\b(cvv|pin|otp|password|api[_ -]?key|bank account|government id)"
        r"\s*(?:is\s+|[:=]\s*)[^\s,;]+",
        r"\1=[REDACTED]",
        text,
    )


def prepare_question(question: str) -> str:
    if not isinstance(question, str) or not question.strip() or len(question) > 4000:
        raise ValueError("Question must contain 1 to 4000 characters.")
    return sanitize_text(question.strip())
