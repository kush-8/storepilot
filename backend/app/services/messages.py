"""Shared PII sanitation and persisted chat message construction."""

from app.agents.guardrails import PIIAgent
from app.storage import now, uid


def sanitize(text):
    result = PIIAgent().sanitize(text)
    return result.sanitized_text, result.pii_detected


def message(role, content):
    return dict(
        message_id=uid(),
        role=role,
        content=sanitize(content)[0][:12000],
        created_at=now().isoformat(),
        pii_checked=True,
    )
