# StorePilot — Engineering Requirements

Version: 2.0 | Status: documents only; no application implementation authorized

## 1. Codebases and stack

Separate frontend/ and backend/. React + TypeScript + Vite + npm frontend; Python 3.12 + uv + FastAPI backend; LangGraph orchestration; Chroma policy vectors; SQLite source and application databases; Docker Compose.

Existing pyproject.toml, uv.lock, Vite scaffold, source importer/database, and starter API remain unchanged. Dependency migration, login/JWT code, agent code, ticket migrations, executable tests, and Docker files are not being implemented during this document phase.

Authoritative proposed API contract: [backend/openapi.json](../backend/openapi.json). API_CONTRACT.md explains it; AUTOMATED_TEST_DESIGN.md specifies future tests.

## 2. Authentication design requested by the user

Login takes employee_id and store_id only. Validate formats and verify the exact assignment against employee_master. Example valid supplied pair: E0001 / ST008. The login store is the employee's assigned store, not necessarily the affected store of an issue.

After a matching pair, issue a signed short-lived JWT. Proposed defaults: HS256 with a high-entropy backend-only key; 30-minute lifetime; bounded 30-second clock skew. Require sub (employee ID), iss=storepilot, aud=storepilot-api, iat, exp, and jti; include store_id as validated session context. Validate signature, fixed allowed algorithm, issuer/audience, times, jti/session state, and current employee assignment on protected requests.

Levels/roles in browser input or token metadata are not authoritative. Lookup the current employee level in the database for authorization. Reassignment invalidates an old assignment session; level changes take effect on the next request. Logout revokes the current jti; no refresh-token flow is planned, so expiry returns the employee to login.

IDs and store IDs identify a directory assignment; they are not secrets and do not prove the human is that employee. This is the requested prototype login, not a claim of strong production identity verification. Do not silently add passwords or another login factor.

Use Authorization: Bearer in the contract; frontend holds the token in memory, clears it on logout/expiry, and avoids localStorage. Do not log tokens or reveal whether the employee ID or store ID was wrong. Generic invalid-login response; planned rate limiting. All of this is a design, not implemented authentication.

## 3. Frontend acceptance

| ID | Requirement |
| --- | --- |
| FE-01 | Login utility view with Employee ID + Store ID; JWT lifecycle and error states |
| FE-02 | Exactly two product destinations: Dashboard and Copilot |
| FE-03 | Dashboard combines visible ticket metrics, filters, list/detail, and embedded Analytics agent questions |
| FE-04 | Copilot is a multi-turn chatbot with focused clarification and ordered recommended steps |
| FE-05 | Show category/priority, concise explanation, citations/evidence, and human route |
| FE-06 | Generate ticket saves a server-held draft; display the ID only after success |
| FE-07 | Refresh dashboard after save; clear prior-employee results on identity changes |
| FE-08 | No Evaluation screen, evaluation widgets, or separate Analytics/Overview page |
| FE-09 | Accessible labels/focus, safe text rendering, responsive 360 px layout |
| FE-10 | No credentials, raw sensitive chat persistence, or direct database/model authority in browser |

Private chatbot history remains owner-only. Permitted ticket viewers see the sanitized report and ticket evidence, not an entire other employee's chat.

## 4. Agent workflow acceptance

Every chat turn and dashboard question: PII -> Safety -> Router. Unsafe requests stop before ordinary retrieval. Router emits a typed route and chooses RAG, Data, Both, clarification, or an appropriate redirect/unsupported result.

RAG queries only supplied policy sections in Chroma. Data executes registered parameterized read-only templates. Analytics owns dashboard questions and calls scoped Data plus optional RAG. Response/rules nodes enforce priority, escalation, grounding, and schema; a deterministic ticket service is the only writer of validated tickets.

- Guardrails re-run on follow-ups, draft edits, retrieved text, and final output.
- Raw sensitive input never reaches model context, logs, checkpoints, messages, drafts, or tickets.
- Policy guidance requires policy evidence. Data-only is allowed for factual lookup/aggregation.
- P1, confidence <0.60, policy conflict, restricted requests, and approval situations require human review.
- Urgent guidance is shown before optional questions; saving a report does not approve a refund/action.
- Missing inventory records mean unknown. Historical labels and root_cause_hint do not bypass independent classification.
- Graph paths and evidence budgets are bounded; at most four retrieved policy sections by default.
- No arbitrary generated SQL, direct model writes, external claim/refund/transfer execution.

## 5. Proposed API surface

All paths are proposed except the earlier starter health/dashboard code. Existing starter dashboard semantics do not yet match employee scoping.

| Method | Path | Purpose |
| --- | --- | --- |
| GET | /api/health | Public capability readiness, no employee/ticket details |
| POST | /api/auth/login | Verify Employee ID + Store ID; issue JWT |
| POST | /api/auth/logout | Revoke current JWT session |
| GET | /api/me | Server-resolved employee context and current level |
| GET | /api/stores | Location options for issue/filter context |
| POST | /api/conversations | Create owner-only issue conversation |
| GET | /api/conversations/{conversation_id} | Read owner's sanitized conversation |
| POST | /api/conversations/{conversation_id}/messages | Guarded turn -> follow-up/recommendation/refusal/draft |
| GET | /api/ticket-drafts/{draft_id} | Owner-only server-held validated draft |
| POST | /api/tickets | Generate ticket from draft ID/revision with Idempotency-Key |
| GET | /api/tickets | Filtered/paginated authorized ticket list |
| GET | /api/tickets/{ticket_id} | Authorized ticket detail, evidence, lifecycle |
| PATCH | /api/tickets/{ticket_id}/status | Creator-only lifecycle change after visibility check |
| GET | /api/dashboard | Authorized ticket aggregates for shared filters/window |
| POST | /api/dashboard/analytics | Guarded natural-language question and scoped follow-up |
| GET | /api/policies/{section_id} | Resolve an allowlisted cited section |

No frontend evaluation or public evaluation-run/results endpoint. Non-streaming JSON is the first contract; token streaming can be designed later.

Errors: 401 missing/invalid/expired token; 404 for hidden/nonexistent resources; 403 for a visible ticket's disallowed mutation; 409 stale draft/idempotency mismatch or concurrent status revision; 422 malformed/invalid request; 429 rate limit; 503 unavailable capability; 504 timeout. Error envelopes contain safe code/message/request ID, never raw prompts, secrets, or unrestricted record details.

## 6. Persistence and integrity

Keep retail.db immutable and read-only. New storepilot.db persists application conversations/messages, drafts, tickets, recommendations/evidence, ticket events, and JWT session/idempotency metadata. Schema design is in TICKET_DATA_MODEL.md; no migration is executed yet.

Ticket creation obtains creator identity from the validated session, loads the exact draft revision, rechecks safety/access and directory references, and writes all records in one transaction. A retried request with the same identity/key/body returns the same ticket; reused key with different draft input returns 409. Re-check draft age/source/access versions; stale drafts require reanalysis.

Confirmed read scope: ticket creator CURRENT level <= viewer CURRENT level. Snapshots at creation are audit fields only. Apply it to reads, list totals, all dashboard aggregates, search, related-ticket evidence, and model context. Browser filters never broaden scope.

Only the creator may change ticket status in the initial design. Being allowed to read another employee's ticket does not permit editing it or approving an operational action. Open -> In Progress/Closed, In Progress -> Open/Closed, and Closed -> Open with a sanitized reason. Record every transition with actor, actual timestamp, expected version, and old/new state.

Historical support cases can seed tickets idempotently with source_case_id and origin=historical_import; preserve recorded-label provenance and explicit unvalidated-policy status. Existing source counts remain 2,970. Never seed evaluation prompts/expected answers as tickets or retrieve them.

## 7. Query, access, and time semantics

Source tables: store_master 50; vendor_master 15; product_master 520; employee_master 100; inventory 1,250; receipts 310; returns_quality 160; support_cases 550; escalation_matrix 15.

Runtime ticket queries can attach the source database read-only for current employee levels. Cross-file foreign references require service validation; within app DB use normal FK checks. Agents read application data through scoped repositories and cannot write.

Live mode: actual server UTC timestamps and captured now. Historical snapshot mode/evaluation: fixed 2026-10-10T12:00:00+05:30; interval (start, end]. Unresolved = Open/In Progress. Imports retain source IST timestamps normalized to UTC; date-only receipts remain dates.

Dashboard and Analytics share normalized filters, employee scope, data mode, and time window. Result row caps are stated; totals are calculated before pagination. Cache keys include employee/access version, filters/window/mode, source hash and application data revision. Clear/revalidate caches after level changes, status changes, and ticket creation.

Quality counts distinguish tickets/support cases from returns; current vendor association is not proof of historical sourcing. Inventory/receipts are source snapshots, not live POS data.

## 8. Evaluation and automated tests

Backend-only evaluator calls the same pipeline in no-write mode. Test RAG retrieval relevance/citation support plus guardrails, routing, multi-turn behaviour, SQL correctness, ticket scoping, and grounded outputs. Expected labels/sources/behaviour remain outside inference. No live ticket creation during evaluation.

Export the required predictions schema order: test_id, category, priority, confidence, answer, citations, data_used, escalated, escalation_team, pii_masked, safety_refusal, notes. Semicolon-separated source lists and Yes/No submission booleans. Save actual metrics/failures/configuration/hashes after running.

AUTOMATED_TEST_DESIGN.md defines unit, repository/API integration, contract, frontend E2E, deployment, and real-model evaluation suites. No executable tests or asserted pass results are delivered in this document phase.

## 9. Operational targets and future dependencies

Targets, not measurements: local SQL under one second on these datasets, model turns capped at 30 seconds, one retry for transient provider failure, scoped output cap 200 rows, no retries for refusal. New dependency planning includes LangGraph, Chroma, and a maintained JWT implementation; versions and manifests remain untouched.

Docker: frontend static server/API proxy, FastAPI backend, private Chroma. Source DB/policies read-only; storepilot.db (including journal files), artifacts, and vector index on separate persistent mounts. Single-backend-process SQLite write concurrency initially; bounded lock retry, transactions, backups, and migrations.

## 10. Review deliverables

PRD.md, APP_FLOW.md, TECH_STACK.md, SYSTEM_DESIGN.md, FRONTEND_DESIGN.md, TICKET_DATA_MODEL.md, API_CONTRACT.md, backend/openapi.json, AUTOMATED_TEST_DESIGN.md. Implementation stays paused.
