"""Local patterns identify spans; they never return the matched sensitive values."""

import re

from ..contracts import PIIKind, Redaction

_EMAIL = re.compile(
    r"(?<![\w.+-])[A-Za-z0-9.!#$%&'*+/=?^_`{|}~-]+@"
    r"[A-Za-z0-9](?:[A-Za-z0-9-]*[A-Za-z0-9])?"
    r"(?:\.[A-Za-z0-9](?:[A-Za-z0-9-]*[A-Za-z0-9])?)+(?![\w-])"
)
_NUMBER = re.compile(r"(?<!\w)\+?\d+(?:[ \t.-]\d+){0,8}(?!\w)")
_PAREN_PHONE = re.compile(
    r"(?<!\w)(?:\+\d{1,3}[ \t.-]*)?\(\d{2,5}\)[ \t.-]*"
    r"\d{3,5}[ \t.-]\d{4,5}(?!\w)"
)
_OPERATIONAL = re.compile(
    r"\b(?:E\d{4}|(?:ST|WH)\d{3}|SKU\d+|REG(?:ISTER)?[-_]\w+|"
    r"(?:RCPT|RQ|CASE|CAS|SP)[-_][A-Za-z0-9_-]+)\b|"
    r"\b[0-9a-f]{8}(?:-[0-9a-f]{4}){3}-[0-9a-f]{12}\b|"
    r"\b\d{4}-\d{2}-\d{2}(?:[T ]\d{2}:\d{2}(?::\d{2}(?:\.\d+)?)?"
    r"(?:Z|[+-]\d{2}:\d{2})?)?\b",
    re.I,
)
_SEPARATOR = r"[\"']?(?P<separator>[ \t]*(?::|=)[ \t]*|[ \t]+is[ \t]+|[ \t]+)"
_VALUE = r"""(?:"(?:\\.|[^"\\\r\n])*"|'(?:\\.|[^'\\\r\n])*'|[^\s,;]+)"""
_NUMERIC_VALUE = r"\+?\d(?:[ \t.-]?\d)*"
_LABELS = (
    (
        PIIKind.SECRET,
        r"cvv|cvc|pin|otp|password|passcode|api[_ -]?key|"
        r"(?:access|refresh|bearer)[_ -]?token|client[_ -]?secret|secret",
    ),
    (PIIKind.ACCOUNT, r"(?:bank[ _-]+)?account(?:[ _-]+(?:number|no))?"),
    (
        PIIKind.GOVERNMENT_ID,
        r"aadhaar|aadhar|pan|passport(?:[ _-]+number)?|"
        r"government[ _-]+id",
    ),
    (PIIKind.CARD, r"(?:payment[ _-]+)?card(?:[ _-]+(?:number|no))?"),
    (PIIKind.PHONE, r"phone(?:[ _-]+number)?|mobile(?:[ _-]+number)?"),
)
_LABEL_PATTERNS = tuple(
    (
        kind,
        re.compile(
            r"\b(?:"
            + labels
            + r")\b"
            + _SEPARATOR
            + r"(?P<value>"
            + _NUMERIC_VALUE
            + "|"
            + _VALUE
            + ")",
            re.I,
        ),
    )
    for kind, labels in _LABELS
)
_BEARER = re.compile(r"\bBearer[ \t]+(?P<value>[A-Za-z0-9._~+/-]{16,}={0,2})", re.I)
_NON_VALUES = frozenset(
    {
        "for",
        "to",
        "the",
        "a",
        "an",
        "is",
        "not",
        "and",
        "or",
        "on",
        "in",
        "of",
        "from",
        "through",
        "please",
        "reset",
        "change",
        "required",
        "authentication",
        "management",
        "request",
        "requests",
        "number",
        "numbers",
        "value",
        "values",
        "card",
        "reader",
    }
)
_STATUS_WORDS = frozenset(
    {
        "suspended",
        "blocked",
        "locked",
        "missing",
        "damaged",
        "expired",
        "disabled",
        "active",
        "invalid",
        "unavailable",
        "required",
        "closed",
        "open",
        "frozen",
    }
)


def _overlaps(a: Redaction, b: Redaction) -> bool:
    return a.start < b.end and b.start < a.end


def _value_span(match, kind):
    start, end = match.span("value")
    value = match.group("value")
    if len(value) >= 2 and value[0] == value[-1] and value[0] in "\"'":
        start, end = start + 1, end - 1
        value = value[1:-1]
    if not value or value.startswith("[REDACTED_"):
        return None
    if kind in (PIIKind.ACCOUNT, PIIKind.GOVERNMENT_ID):
        if value.casefold().rstrip(".?!") in _STATUS_WORDS:
            return None
    if "separator" in match.re.groupindex:
        if not match.group("separator").strip() and value.casefold().rstrip(".?!") in _NON_VALUES:
            return None
    if kind in (PIIKind.CARD, PIIKind.PHONE):
        digits = sum(c.isdigit() for c in value)
        if not (digits >= 13 if kind == PIIKind.CARD else 10 <= digits <= 15):
            return None
    return Redaction(kind, start, end)


def detect(text: str) -> tuple[Redaction, ...]:
    candidates = []
    for kind, pattern in _LABEL_PATTERNS:
        for match in pattern.finditer(text):
            if span := _value_span(match, kind):
                candidates.append((100, span))
    for match in _BEARER.finditer(text):
        candidates.append((100, Redaction(PIIKind.SECRET, *match.span("value"))))
    for match in _EMAIL.finditer(text):
        candidates.append((80, Redaction(PIIKind.EMAIL, *match.span())))

    scan_chars = list(text)
    for match in _OPERATIONAL.finditer(text):
        # Preserve offsets while preventing a nearby identifier/date from swallowing
        # an adjacent sensitive number into one excluded numeric candidate.
        scan_chars[match.start() : match.end()] = "_" * (match.end() - match.start())
    numeric_text = "".join(scan_chars)
    for pattern in (_NUMBER, _PAREN_PHONE):
        for match in pattern.finditer(numeric_text):
            digits = sum(c.isdigit() for c in match.group())
            if 10 <= digits <= 12 or (match.group().startswith("+") and 10 <= digits <= 15):
                kind = PIIKind.PHONE
            elif digits >= 13:
                kind = PIIKind.CARD
            else:
                continue
            span = Redaction(kind, *match.span())
            candidates.append((20, span))

    # Prefer labelled interpretations (e.g. account/Aadhaar) over generic numeric ones.
    candidates.sort(key=lambda pair: (-pair[0], -(pair[1].end - pair[1].start), pair[1].start))
    chosen = []
    for _, span in candidates:
        if not any(_overlaps(span, existing) for existing in chosen):
            chosen.append(span)
    return tuple(sorted(chosen, key=lambda span: span.start))
