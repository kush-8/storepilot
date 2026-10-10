"""Immutable agent results contain sanitized text and metadata, never matched values."""

from dataclasses import dataclass
from enum import StrEnum


class PIIKind(StrEnum):
    EMAIL = "email"
    PHONE = "phone"
    CARD = "card"
    SECRET = "secret"
    ACCOUNT = "account"
    GOVERNMENT_ID = "government_id"


@dataclass(frozen=True, slots=True)
class Redaction:
    kind: PIIKind
    start: int
    end: int


@dataclass(frozen=True, slots=True)
class PIIResult:
    sanitized_text: str
    redactions: tuple[Redaction, ...]

    @property
    def pii_checked(self) -> bool:
        return True

    @property
    def pii_detected(self) -> bool:
        return bool(self.redactions)


class SafetyAction(StrEnum):
    ALLOW = "allow"
    REFUSE = "refuse"


class SafetySignal(StrEnum):
    PROMPT_INJECTION = "prompt_injection"
    RESTRICTED_DATA_REQUEST = "restricted_data_request"
    CONTROL_BYPASS = "control_bypass"
    UNSAFE_DATA_HANDLING = "unsafe_data_handling"
    URGENT_SAFETY = "urgent_safety"


@dataclass(frozen=True, slots=True)
class SafetyResult:
    action: SafetyAction
    signals: tuple[SafetySignal, ...]
    priority_override: str | None
    escalation_required: bool
    human_review_required: bool
    safe_response: str | None

    @property
    def allowed(self) -> bool:
        return self.action == SafetyAction.ALLOW
