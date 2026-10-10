# StorePilot — OpenAPI Summary and Contract Notes

Version: 2.2 | Status: backend workflow/API connected and tests green; frontend/evaluation work remains

Current implementation and verified coverage: [Copilot workflow and tests](COPILOT_WORKFLOW_AND_TESTS.md). The detailed design below includes planned requirements; the current report distinguishes implemented behavior from remaining work.


## 1. What the document is

[backend/openapi.json](../backend/openapi.json) is a machine-readable OpenAPI 3.1.0 contract for the StorePilot backend: **16 operations across 15 paths, with 35 reusable schemas**. It describes requests, responses, JWT protection, validation and errors. FastAPI serves this maintained contract; executable routes live in backend/app/main.py.

All 16 operations are now registered. Copilot uses the guarded agent workflow and Dashboard Analytics uses the same DataAgent. Live model verification awaits GROQ_API_KEY configuration; see the linked report for test results.

## 2. Plain-English endpoint summary

| Group | Operations | What the frontend can do |
| --- | ---: | --- |
| Health | 1 | Check whether database/chat/retrieval capabilities are available |
| Authentication/profile | 3 | Log in with Employee ID + Store ID, get current employee context, and log out |
| Location context | 1 | Load store/warehouse options |
| Copilot conversations | 3 | Start a private chat, read its sanitized history, and send issue/follow-up messages |
| Ticket draft | 1 | Read the server-held proposed ticket before saving |
| Tickets | 4 | Generate, list, inspect, and update the creator's ticket status |
| Dashboard | 2 | Load permitted workload summaries and ask the integrated Analytics agent questions |
| Policy evidence | 1 | Open an existing cited policy section |

There is no frontend/public evaluation API. RAG/pipeline evaluation remains a backend CLI/test workflow.

## 3. Login and authorization

POST /api/auth/login accepts employee_id and store_id. The backend verifies their exact employee_master assignment and returns a signed JWT plus role/current level. Example supplied assignment: E0001 / ST008. The affected store of an issue can differ from the login store.

Protected requests use Authorization: Bearer <JWT>. Proposed token lifetime is 30 minutes, using HS256 with a backend-only signing key and issuer/audience validation. Check expiry, revocation and current directory assignment; fetch current levels separately. Logout revokes the session; expiry requires login again. No password or refresh-token flow is specified.

The requested ID/store pair identifies an employee assignment but is not a secret proof of human identity. This is the prototype login the user selected.

Confirmed ticket-read rule: creator current level <= viewer current level. Level 1 sees level-1 creators; level 2 sees 1–2; level 3 sees 1–3; level 4 sees 1–4. This applies to every ticket-derived list, count, chart, search, detail, related record and model evidence. Inaccessible and nonexistent resources return the same not-found response.

## 4. Chat-to-ticket sequence

1. POST /api/conversations opens an owner-only issue thread.
2. POST /api/conversations/{conversation_id}/messages sends an issue or follow-up. Each turn runs PII -> Safety -> Triage -> Router -> RAG/Data/Both as needed.
3. The response can contain clarification, recommended steps, refusal, dashboard redirect, or a grounded server-held ticket draft.
4. GET /api/ticket-drafts/{draft_id} retrieves the owner draft and generation_allowed flag.
5. POST /api/tickets sends draft_id + draft_revision and Idempotency-Key.
6. A committed first save returns 201 and a ticket ID; the same retry returns 200 with the existing ticket.
7. GET /api/tickets/{ticket_id} opens the authorized report, steps, citations/evidence, route and event history.

Messages use a client_message_id to identify retries. A materially edited issue is sent as a new guarded chat turn; it produces a new draft revision. The client cannot set creator identity/level, priority, model SQL, or approval authority through the create-ticket payload.

Private conversation history is owner-only even when the generated ticket is visible to other employees. Ticket creation records the issue; it does not notify external teams or approve refunds/transfers/claims.

## 5. Combined dashboard and Analytics

GET /api/dashboard returns scoped totals and distributions. GET /api/tickets returns the same scoped filtered records with pagination. POST /api/dashboard/analytics accepts a natural-language question, filters, and optional owner-only analytics thread ID, then returns grounded answers or clarification/refusal.

Shared filters: live/historical mode, last24h/last7d/last30d/all window or explicit start/end, store, SKU, status, priority and category. Start/end must be provided together and cannot be combined with a window preset.

Live mode uses actual server timestamps. Historical snapshot mode uses imported cases and the fixed 10 October 2026 noon IST cutoff. Responses identify the resolved window, current visibility scope and source versions. Analytics rows are capped at 200 and explicitly marked when truncated; aggregate calculations use the full authorized matching set.

Creator-only status changes require expected_version and create an audit event. Reopening a closed ticket requires a reason. Viewing peers' tickets is not permission to edit them.

## 6. Important schemas

EmployeeContext, LoginRequest/Response, Conversation, MessageRequest, ChatTurn, Draft, TicketSummary/Detail, TicketCreated, Dashboard, AnalyticsRequest/Response, Citation, Evidence, Escalation, GuardrailFlags and Error.

Typed fields let the UI render follow-up messages, recommendations and draft/receipt cards without interpreting free-form prose. No hidden model reasoning or raw sensitive prompts are part of the contract.

## 7. Error meanings

| Status | Meaning |
| --- | --- |
| 401 | Invalid login/JWT, expiry, revocation or changed assignment |
| 403 | Ticket is visible but mutation is not permitted |
| 404 | Resource missing or inaccessible |
| 409 | Stale draft/version, conflicting retry, duplicate draft or invalid transition |
| 422 | Invalid body, identifier or filters |
| 429 | Request rate limit; Retry-After |
| 503 | Required service unavailable |
| 504 | Bounded model/retrieval timeout |

Errors use safe code/message/request_id, not raw secrets or internal SQL details. Successful refusal/clarification is a structured 200 response, not an infrastructure error.

## 8. Document validation versus implementation testing

During this document phase, check JSON parsing, local references, unique operation IDs, path parameters, security declarations and schema consistency. That does not prove FastAPI behaviour. AUTOMATED_TEST_DESIGN.md plans later contract, repository/API, frontend and model-evaluation suites.

Document review completed: JSON parsed; all 127 local reference occurrences resolve; 16 operation IDs are unique; templated path parameters match; only health/login opt out of JWT; no evaluation endpoint exists. No structural errors were found in these checks. A full OpenAPI conformance validator and application/test execution are deferred.

## 9. Primary format references

Contract format: [OpenAPI 3.1.0 specification](https://spec.openapis.org/oas/v3.1.0.html). Token vocabulary: [RFC 7519 — JSON Web Token](https://www.rfc-editor.org/rfc/rfc7519). Token lifetime, algorithm and endpoint design here are project choices, not claims that these standards mandate those choices.
