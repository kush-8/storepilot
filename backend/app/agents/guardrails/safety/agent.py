"""Stateless decision entry point consumes only a typed PII result."""

from ..contracts import PIIResult, SafetyAction, SafetyResult, SafetySignal
from ..normalization import normalize_text
from .rules import classify

_REFUSAL = (
    "I cannot disclose restricted information, bypass controls or collect sensitive payment "
    "data. Use the approved process and contact Security/POS Support for human review."
)
_URGENT_GUIDANCE = (
    "Keep people away from the affected equipment or unsafe area. Immediately contact the "
    "Store Manager and the appropriate safety support team; human review is required."
)


class SafetyAgent:
    def evaluate(self, pii_result: PIIResult) -> SafetyResult:
        if not isinstance(pii_result, PIIResult):
            raise TypeError("Safety input must be a PIIResult")
        text = normalize_text(pii_result.sanitized_text)
        signals = classify(text)
        refused = any(signal != SafetySignal.URGENT_SAFETY for signal in signals)
        urgent = SafetySignal.URGENT_SAFETY in signals
        return SafetyResult(
            action=SafetyAction.REFUSE if refused else SafetyAction.ALLOW,
            signals=signals,
            priority_override="P1" if refused or urgent else None,
            escalation_required=refused or urgent,
            human_review_required=refused or urgent,
            safe_response=_REFUSAL if refused else _URGENT_GUIDANCE if urgent else None,
        )
