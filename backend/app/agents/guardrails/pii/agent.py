"""Stateless PII entry point with no model, database or HTTP dependency."""

from ..contracts import PIIResult
from ..normalization import normalize_text
from .detectors import detect
from .redaction import redact


class PIIAgent:
    def sanitize(self, text: str) -> PIIResult:
        normalized = normalize_text(text)
        spans = detect(normalized)
        return PIIResult(sanitized_text=redact(normalized, spans), redactions=spans)
