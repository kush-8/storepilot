"""PII acceptance cases for the separately implemented local agent."""

import json
from dataclasses import asdict

import pytest

from tests.support import boundary


def sanitize(text):
    return boundary("app.agents.guardrails", "PIIAgent")().sanitize(text)


@pytest.mark.parametrize(
    "value,kind",
    [
        ("customer.name@example.com", "email"),
        ("9876543210", "phone"),
        ("+91 98765 43210", "phone"),
        ("(212) 555-1234", "phone"),
        ("4111 1111 1111 1111", "card"),
        ("4111-1111-1111-1111", "card"),
        ("3782 822463 10005", "card"),
        ("1234567890123456", "card"),
    ],
)
def test_sensitive_values_are_redacted_without_requiring_valid_card_checksum(value, kind):
    result = sanitize(f"Reader failed. Customer supplied {value}.")
    assert value not in result.sanitized_text
    assert result.pii_checked and result.pii_detected
    assert kind in {span.kind for span in result.redactions}
    assert "Reader failed" in result.sanitized_text


@pytest.mark.parametrize(
    "text,value,kind",
    [
        ("CVV: 123", "123", "secret"),
        ("PIN=4321", "4321", "secret"),
        ("OTP is 987654", "987654", "secret"),
        ("password hunter2", "hunter2", "secret"),
        ('password = "space secret"', "space secret", "secret"),
        ("api_key: sk-test-123456789012", "sk-test-123456789012", "secret"),
        ("access token: abc.def.ghi", "abc.def.ghi", "secret"),
        (
            "Authorization: Bearer eyJhbGciOiJIUzI1NiJ9.test.signature",
            "eyJhbGciOiJIUzI1NiJ9.test.signature",
            "secret",
        ),
        ("bank account: 123456789012", "123456789012", "account"),
        ("Aadhaar: 1234 5678 9012", "1234 5678 9012", "government_id"),
        ("PAN: ABCDE1234F", "ABCDE1234F", "government_id"),
        ("government ID: ID-PRIVATE-456", "ID-PRIVATE-456", "government_id"),
    ],
)
def test_labelled_values_keep_their_type_but_remove_the_value(text, value, kind):
    result = sanitize(text)
    assert value not in result.sanitized_text
    assert {span.kind for span in result.redactions} == {kind}
    assert result.sanitized_text.count("[REDACTED_") == 1


@pytest.mark.parametrize(
    "text",
    [
        "Employee E0001 at ST003: SKU1001, warehouse WH001, register REG-1234567890.",
        "Ticket SP-1234567890123; receipt RCPT-1234567890; return RQ-1234567890.",
        "Request 123e4567-e89b-42d3-a456-123456789012; quantity 50; refund INR 5000.",
        "The issue started at 2026-10-10T12:00:00+05:30.",
        "How do I reset a POS password? Do not ask for PIN or OTP.",
        "A customer was injured by a treadmill demo unit.",
        "",
        "सुरक्षित स्टोर संचालन",
    ],
)
def test_operational_identifiers_and_safe_context_are_preserved(text):
    result = sanitize(text)
    assert result.sanitized_text == text
    assert not result.pii_detected and result.redactions == ()


def test_result_and_metadata_never_retain_original_sensitive_values():
    result = sanitize("Phone 9876543210; email a@b.com; password='secret phrase'.")
    metadata = json.dumps(asdict(result)) + repr(result)
    for value in ("9876543210", "a@b.com", "secret phrase"):
        assert value not in metadata
    assert len(result.redactions) == 3
    for span in result.redactions:
        assert 0 <= span.start < span.end
        assert not hasattr(span, "value")


def test_overlapping_card_and_label_detections_produce_one_redaction():
    result = sanitize("card number: 4111 1111 1111 1111; error E42.")
    assert result.sanitized_text == "card number: [REDACTED_CARD]; error E42."
    assert len(result.redactions) == 1


def test_normalized_and_zero_width_obfuscated_sensitive_values_are_redacted():
    result = sanitize("Phone ９８７６５４３２１０; email a\u200b@b.com.")
    assert "9876543210" not in result.sanitized_text
    assert "a@b.com" not in result.sanitized_text
    assert {span.kind for span in result.redactions} == {"phone", "email"}


def test_redaction_is_idempotent():
    first = sanitize("Phone 9876543210; password: hunter2; card 4111111111111111.")
    second = sanitize(first.sanitized_text)
    assert second.sanitized_text == first.sanitized_text
    assert not second.pii_detected and second.redactions == ()


@pytest.mark.parametrize(
    "text,raw",
    [
        ("2026-10-10 9876543210", "9876543210"),
        ("2026-10-10 1234 5678 9012", "1234 5678 9012"),
        ("REG-1234567890 9876543210", "9876543210"),
        ("4111 1111 1111 1111 5555 5555 5555 4444", "4111 1111 1111 1111"),
    ],
)
def test_adjacent_dates_ids_and_numeric_values_cannot_hide_sensitive_data(text, raw):
    result = sanitize(text)
    assert raw not in result.sanitized_text
    assert result.pii_detected
    if text.startswith("2026"):
        assert result.sanitized_text.startswith("2026-10-10 ")
    if text.startswith("REG"):
        assert result.sanitized_text.startswith("REG-1234567890 ")


def test_account_and_id_status_words_are_not_treated_as_sensitive_values():
    text = "Account is suspended; passport is missing; PAN card is damaged."
    result = sanitize(text)
    assert result.sanitized_text == text and not result.pii_detected


def test_quoted_secrets_are_fully_redacted_and_json_quotes_are_preserved():
    result = sanitize('{"password": "normal secret", "api_key": "abc123", "store": "ST003"}')
    assert json.loads(result.sanitized_text) == {
        "password": "[REDACTED_SECRET]",
        "api_key": "[REDACTED_SECRET]",
        "store": "ST003",
    }


def test_labelled_adjacent_card_runs_are_fully_removed():
    result = sanitize("card number: 4111 1111 1111 1111 5555 5555 5555 4444")
    assert result.sanitized_text == "card number: [REDACTED_CARD]"


@pytest.mark.parametrize("value", [None, 123, {"content": "private"}])
def test_invalid_inputs_have_safe_type_errors(value):
    with pytest.raises(TypeError, match="must be a string"):
        sanitize(value)


def test_input_size_is_bounded_without_echoing_the_input():
    with pytest.raises(ValueError, match="maximum") as caught:
        sanitize("PRIVATE_SENTINEL " * 2000)
    assert "PRIVATE_SENTINEL" not in str(caught.value)
