# Standalone PII and Safety agents

These agents are implemented separately from the API. They use local deterministic patterns and standard-library contracts. They have no HTTP, SQLite, model, retrieval or filesystem calls. Existing `app/copilot.py`, routes and manifests are untouched, so requests to the current API still use its earlier checks.

## Folder structure and responsibilities

```text
app/agents/
  __init__.py
  guardrails/
    __init__.py          # Public imports
    contracts.py         # Immutable PIIResult, SafetyResult, enums and span metadata
    normalization.py     # Input type/size validation and Unicode normalization
    pii/
      __init__.py
      agent.py           # PII entry point: normalize -> detect -> redact
      detectors.py       # Pattern definitions, candidate spans and overlap resolution
      redaction.py       # Replacement rendering only
    safety/
      __init__.py
      agent.py           # Map risk signals into allow/refuse and human-review decisions
      rules.py           # Injection, restricted-data, bypass, handling and urgency rules
    README.md

tests/agents/guardrails/
  test_pii_agent.py
  test_safety_agent.py
  test_isolation.py
```

Detection does not write data or make safety decisions. Redaction does not classify intent. Safety rules identify signals; the Safety agent applies the decision contract. The API and future graph orchestration will be separate callers when integration is authorized.

## Use directly

From the backend directory:

```python
from app.agents.guardrails import PIIAgent, SafetyAgent

pii_result = PIIAgent().sanitize("One reader failed at ST003. Customer phone: 9876543210.")
safety_result = SafetyAgent().evaluate(pii_result)

assert "9876543210" not in pii_result.sanitized_text
assert pii_result.pii_checked and pii_result.pii_detected
assert safety_result.allowed
```

Flow: **text → PIIResult → SafetyResult**. The Safety agent requires a `PIIResult`, which helps callers enforce order; it rejects raw-string input. A manually constructed result is not a verified security credential. Callers must use the PII agent for each new message, follow-up, retrieved text and outgoing text they want checked. These modules do not automatically walk stored history or structured payloads.

Both agents are stateless. One safe turn cannot grant permission to a later turn. Do not persist/checkpoint the original input. Later orchestration must use `sanitized_text` and safe metadata and obey the refusal before invoking ordinary tools. There is no LangGraph runtime or API integration in this phase.

## PII contract and behaviour

`PIIAgent.sanitize(text)` returns:

| Field | Meaning |
| --- | --- |
| sanitized_text | Normalized text with sensitive spans replaced |
| redactions | Immutable tuple of kind/start/end metadata; no matched value |
| pii_checked | Computed property, always true for a completed result |
| pii_detected | Computed property, true when a value was redacted |

Computed properties are accessed on the result; `dataclasses.asdict()` serializes dataclass fields only. Redaction offsets refer to the normalized input, before replacement, not the returned text or original unnormalized input.

Coverage: emails, common phones, card-like digit sequences, labelled CVV/PIN/OTP/password/API keys/tokens, bearer credentials, labelled bank accounts and government IDs. Full redaction uses `[REDACTED_EMAIL]`, `[REDACTED_PHONE]`, `[REDACTED_CARD]`, `[REDACTED_SECRET]`, `[REDACTED_ACCOUNT]` and `[REDACTED_GOVERNMENT_ID]`. Phone/email examples in the source policy show partial masking; this first implementation uses full redaction.

Number redaction does not depend on a valid card checksum. Long or adjacent numeric groups are handled conservatively, including runs beyond a normal card length. Employee/store/warehouse/SKU/register/ticket/receipt IDs, UUIDs and ISO dates are excluded from generic numeric detection; an explicit sensitive label still takes precedence. Quoted values retain their quotes. Overlapping detections produce one replacement, and already-redacted input is idempotent.

Input is bounded to 20,000 characters before and after normalization. NFKC normalization handles compatibility/full-width characters; invisible Unicode format characters are removed for detection. This can change legitimate text too. Bare numeric sequences can be ambiguous; tests cover specified retail identifiers and dates, not every possible record format.

Semantic detection of arbitrary person names, addresses and health details is outside this approved first method. Unlabelled arbitrary secrets and every possible phone/ID format are not recognized. Choosing a broader entity-recognition method remains a separate decision.

## Safety contract and behaviour

`SafetyAgent.evaluate(pii_result)` returns:

| Field | Meaning |
| --- | --- |
| action / allowed | allow or refuse; allowed is a computed property |
| signals | prompt_injection, restricted_data_request, control_bypass, unsafe_data_handling or urgent_safety |
| priority_override | P1 for refused requests or detected urgent physical risk; otherwise null |
| escalation_required / human_review_required | Flags for the caller; no escalation is executed |
| safe_response | Fixed refusal/urgent guidance, or null for ordinary allowed input |

Restricted-data requests, malicious overrides, bypass instructions and unsafe collection/storage instructions are refused. The fixed response contains no user-supplied values. Urgent injury, unsafe equipment, recall notice or electric shock reports remain allowed with P1 and immediate human guidance. Ordinary safety coaching and negated commands remain allowed within the covered English rules; a later unsafe command is independently detected.

These are bounded local patterns, not a semantic classifier. The agent does not grant data access, approve an action, generate a ticket, contact anyone or run a tool. Authorization and other business rules remain downstream responsibilities. Broad paraphrase/multilingual intent detection needs separate coverage and method approval.

## Tests and TDD evidence

```powershell
.\.venv\Scripts\python.exe -m pytest tests/agents/guardrails -q
.\.venv\Scripts\python.exe -m ruff check app/agents tests/agents
```

The initial 68 cases failed before production modules were created. They passed after implementation. Additional tests exposed adjacent-number and account-status redaction defects; regression cases were added and those defects were corrected. The isolation test imports/runs the agents in a fresh Python process and verifies that API, persistence and model modules are not imported.

Latest standalone result on 10 October 2026: **76 passed, zero failures/errors/skips**. Ruff checks across `app`, `scripts` and `tests` passed. The test process emitted the existing Starlette/httpx deprecation warning from the parent test configuration; the standalone agents do not import those packages.

The wider backend suite still has the previously reported authentication-fixture and missing orchestration/evaluation failures. Passing these standalone checks does not mean the API is using these agents.
