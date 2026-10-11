"""Explicit local safety patterns; policy and metadata remain separate from decisions."""

import re

from ..contracts import SafetySignal

_RESTRICTED = (
    r"(?:full |unmasked )?(?:customer['’]?s? )?(?:card numbers?|payment data|"
    r"phone numbers?|emails?|bank accounts?|government ids?)|"
    r"cvv|cvc|pin|otp|passwords?|credentials|(?:access |payment )?tokens?|secrets?|"
    r"(?:full |private )?customer (?:database|records|data)|private records|"
    r"supplier (?:contract |confidential )?(?:prices?|pricing)|contracts?|"
    r"(?<!\w)\.env\b|/etc/passwd|restricted files|"
    r"\[redacted_(?:card|secret|account|government_id)\]"
)
_REQUEST = re.compile(
    r"\b(?:show|give|print|export|reveal|send|list|access|unmask|retrieve|expose|"
    r"read|display|share|dump|extract|get|open)\b[^\n.!?;]{0,100}(?:" + _RESTRICTED + ")",
    re.I,
)
_INJECTION = (
    re.compile(
        r"\b(?:ignore|disregard|forget)\s+(?:(?:all|the|previous|prior|system|"
        r"developer|safety|security|your)\s+){0,5}(?:instructions|rules|controls)\b",
        re.I,
    ),
    re.compile(
        r"\b(?:reveal|show|print|send)\b[^\n.!?;]{0,60}"
        r"(?:hidden (?:system |judge |developer )?(?:prompts?|test cases)|"
        r"system prompt|developer prompt)\b",
        re.I,
    ),
    re.compile(
        r"\b(?:invent|fabricate)\b[^\n.!?;]{0,35}(?:policy|policies|sources|citations)\b", re.I
    ),
)
_BYPASS = re.compile(
    r"\b(?:bypass|skip|disable|turn off)\b[^\n.!?;]{0,45}"
    r"(?:safety|security|controls|approval|audit|logging|guardrails)\b",
    re.I,
)
_HANDLING = re.compile(
    r"\b(?:write|record|store|log|save|collect|ask for)\b(?:\s+|:\s*)"
    r"[^\n.!?;]{0,80}(?:" + _RESTRICTED + ")",
    re.I,
)
_SUSPICIOUS = re.compile(r"\bsuspicious request\b[^\n.!?;]{0,60}\brestricted\b", re.I)
_URGENT = re.compile(
    r"\binjur(?:y|ies|ed)\b|\belectric shock\b|\bsparking\b|\brecall notice\b|"
    r"\bunsafe\s+(?:treadmill|demo|equipment|machine|product|helmet|fitness)\b|"
    r"\b(?:equipment|machine|products?|helmets?)\b[^\n.!?;]{0,30}\b(?:is|are) unsafe\b",
    re.I,
)
_NEGATED = re.compile(
    r"\b(?:do not|don't|never|should not|must not|not to|avoid|refuse to|cannot|won't)"
    r"\s+(?:\w+\s+){0,2}$",
    re.I,
)


def _positive_match(pattern, text):
    for match in pattern.finditer(text):
        prefix = re.split(r"[.!?;\n]", text[max(0, match.start() - 60) : match.start()])[-1]
        if not _NEGATED.search(prefix):
            return True
    return False


def classify(text: str) -> tuple[SafetySignal, ...]:
    signals = []
    if any(_positive_match(pattern, text) for pattern in _INJECTION):
        signals.append(SafetySignal.PROMPT_INJECTION)
    if _positive_match(_REQUEST, text) or _SUSPICIOUS.search(text):
        signals.append(SafetySignal.RESTRICTED_DATA_REQUEST)
    if _positive_match(_BYPASS, text):
        signals.append(SafetySignal.CONTROL_BYPASS)
    if _positive_match(_HANDLING, text):
        signals.append(SafetySignal.UNSAFE_DATA_HANDLING)
    if _positive_match(_URGENT, text):
        signals.append(SafetySignal.URGENT_SAFETY)
    return tuple(signals)
