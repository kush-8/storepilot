"""Apply non-overlapping detections without retaining original values in results."""

from ..contracts import Redaction


def redact(text: str, spans: tuple[Redaction, ...]) -> str:
    parts = []
    cursor = 0
    for span in spans:
        if not (cursor <= span.start < span.end <= len(text)):
            raise ValueError("Invalid or overlapping redaction spans")
        parts.append(text[cursor : span.start])
        parts.append(f"[REDACTED_{span.kind.value.upper()}]")
        cursor = span.end
    parts.append(text[cursor:])
    return "".join(parts)
