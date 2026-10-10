# StorePilot — Ticket and Conversation Data Model

Version: 1.0 | Proposed normalized schema; current runtime uses SQLite JSON records

Current persistence is implemented in `backend/app/storage.py` using `sessions`, `records`,
`receipts`, `turns` and `rate_limits`. Tickets retain structured steps, citations, evidence,
escalation and events inside their JSON payload. The tables below describe a future normalized
layout and are not deployed migrations. See [current workflow report](COPILOT_WORKFLOW_AND_TESTS.md).

## 1. Persistence boundary

retail.db retains the immutable nine-CSV import. storepilot.db is a new writable SQLite application database. Rebuilding the source snapshot cannot delete app tickets. Chroma is policy retrieval only.

The application connection may attach retail.db read-only as retail for employee-level joins. SQLite FK constraints cannot span files; validate employee/store/SKU references in services and fail closed for unknown directory identities. Enforce ordinary foreign keys for all application-table links.

## 2. Proposed tables

| Table | Principal fields | Purpose |
| --- | --- | --- |
| auth_sessions | jti_hash PK, employee_id, assigned_store_id, issued_at_utc, expires_at_utc, revoked_at_utc nullable | JWT session/revocation metadata; never store the bearer token |
| conversations | conversation_id PK, owner_employee_id, affected_store_id nullable, created_at_utc, updated_at_utc, version | Owner-only chatbot thread |
| conversation_messages | message_id PK, conversation_id FK, client_message_id nullable, turn_sequence, role, sanitized_content, pii_checked, safety_status, created_at_utc | Persist sanitized dialogue; unique conversation/sequence and conversation/client-message ID for retry handling |
| ticket_drafts | draft_id PK, conversation_id FK, owner_employee_id, revision, sanitized_payload_json, validation_status, source_version, access_version, created_at_utc, expires_at_utc | Immutable revisions of server-controlled proposed tickets |
| tickets | ticket_id PK, conversation_id FK nullable, draft_id FK nullable, draft_revision nullable, created_by_employee_id, creator_level_at_creation, creator_role_at_creation, store_id, sku nullable, register_id nullable, title, description, category, priority, priority_provenance, confidence nullable, status, impact_summary, escalation_team nullable, escalation_channel nullable, sla_minutes nullable, review_required, approval_required, approval_status, origin, source_case_id nullable unique, policy_validation_status, created_at_utc, updated_at_utc, closed_at_utc nullable, version | Authoritative report, classification, workflow and lifecycle |
| ticket_steps | ticket_id FK, step_order, sanitized_instruction | Ordered grounded recommendations |
| ticket_citations | ticket_id FK, section_id, filename, heading_slug, source_hash | Valid policy evidence with index version |
| ticket_evidence | evidence_id PK, ticket_id FK, source_table, source_record_id nullable, query_template_id nullable, sanitized_summary_json, source_hash nullable, observed_at_utc | Bounded operational evidence, not copied unrestricted source rows |
| ticket_events | event_id PK, ticket_id FK, actor_employee_id, event_type, old_status nullable, new_status nullable, sanitized_note nullable, created_at_utc, ticket_version | Append-only creation/status/review history |
| idempotency_receipts | employee_id + idempotency_key PK, request_digest, ticket_id FK, response_status, created_at_utc | Stable creation receipt for retries |
| analytics_threads | analytics_thread_id PK, owner_employee_id, created_at_utc, updated_at_utc, sanitized_context_json | Owner-only dashboard follow-up context; optional persistence |

All fields marked ID are opaque generated identifiers except logical source IDs. Boolean flags are 0/1 in SQLite. New timestamps are UTC ISO strings; money in future app fields uses integer paise/Decimal. Do not invent refund-paid/claim-submitted fields with implied completion.

Draft JSON is schema-validated and sanitized; core ticket fields, ordered steps, citations, and evidence are structured so analytics does not have to parse narrative text. Keep concise classification reasoning, not hidden model reasoning.

## 3. Constraints and indexes

- Ticket priority enum P1–P4; category enum the eight supplied issue categories; status Open/In Progress/Closed.
- Origin enum copilot/historical_import; priority_provenance policy_validated/historical_label; policy_validation_status validated/unvalidated.
- confidence in [0,1] when present. Imported labels have no invented confidence.
- approval_status not_required/pending; initial design has no approve-refund endpoint. Review/escalation can remain required while the report ticket is saved.
- creator_level_at_creation is an audit snapshot. Current creator/viewer employee levels govern access.
- Unique source_case_id prevents duplicate historical imports. Unique draft ID/revision on committed tickets prevents repeated generation of the same draft under different request keys.
- Steps ordered uniquely per ticket; citations deduplicated per ticket/section; child records cannot outlive a referenced ticket.
- Index tickets on (created_by_employee_id, created_at_utc), (status, priority, created_at_utc), (store_id, sku, created_at_utc), (origin, created_at_utc), source_case_id, and version where needed.
- Index messages/events by parent and ordered sequence/time; auth sessions by expiry/revocation.
- Database migrations are versioned; app backup and restore include tickets and child tables.

## 4. Ticket creation transaction

1. Verify JWT/session; obtain creator employee ID from sub and current directory lookup.
2. Load owner-only draft/revision; reject expired, changed, unsafe, or unvalidated drafts.
3. Validate affected store/product logical references. Use trusted server classification/routing, not browser-submitted priority or identity.
4. Check idempotency receipt. Same request returns original ticket; different digest for reused key returns conflict.
5. In one transaction insert ticket, ordered steps, citations, evidence, creation event, and receipt; enforce unique draft/revision.
6. Commit before returning creation success. Roll back all children on failure.
7. Invalidate scoped dashboard data revision and analytics caches.

A report can be saved while an operational action is pending human approval. Creating the ticket does not submit a claim, notify a queue externally, approve a refund, or change inventory.

## 5. Status lifecycle

Creator-only mutation is the initial policy. Visibility alone is insufficient for mutation.

Open -> In Progress/Closed; In Progress -> Open/Closed; Closed -> Open with an explicit sanitized reason. Expected version provides optimistic concurrency. Same-state updates are invalid transitions rather than extra events. Closing sets closed_at_utc; reopening clears it. Every transition writes an event atomically and increments version.

Other employees' status-edit/assignment/approval rights are not inferred from escalation level; add them only after defining an explicit workflow permission.

## 6. Authorization and private context

Every ticket read uses:
current creator level <= current viewer level.

Enforce before search, pagination, aggregates, joins, model evidence, and direct-ID lookup. Unknown creator/viewer levels deny access. Store the numeric snapshots for audit but never authorize against them. Assignee/team/priority cannot widen access.

Conversations, messages, drafts, and analytics threads are owner-only. A visible ticket provides its sanitized report/evidence, not the entire underlying conversation. A linked evidence record referring to another ticket is rechecked against current access before display/model use; stale stored evidence is not an access bypass.

Sanitize and minimize evidence. Do not retain hidden ticket text inside a broadly visible ticket summary. Cache only evidence whose access dependencies can be revalidated.

## 7. Historical case seeding

Optional setup job maps all 550 support_cases into application tickets with deterministic import IDs/source_case_id and original creator employee_id, timestamps, store/SKU/register, category/priority/status. Convert source local IST timestamps to UTC; preserve recorded-label provenance and unvalidated policy status.

Do not invent recommendations, citations, confidence, status-change times, approvals, private conversations, or historic employee-level snapshots. Historical closed tickets have unknown closed_at_utc unless supplied. Root-cause hints remain excluded from classifier input.

Seeding is idempotent and never overwrites live application tickets. Dashboard application metrics use the tickets table, not tickets plus original cases counted again. Evaluation uses immutable support_cases and does not read modified app statuses. Related source evidence must not double count a seeded source_case_id.

Known label conflicts, such as restricted-data requests recorded as P3/P4, remain marked historical until explicitly reassessed; new reports use current safety/policy validation.

## 8. JWT metadata

The requested login validates employee_id/store_id against the source directory, then creates a signed JWT and session row. JWT claims include sub, iss, aud, iat, exp, jti, and assigned store context. Store only a digest of jti/session identifiers as appropriate; never the raw JWT.

Check session revocation, expiry, employee existence, and assignment on each protected request. Current levels are fetched separately. Proposed expiry is 30 minutes; logout revokes the current session. No refresh flow or password fields are added to this requested prototype design.

## 9. Time and analytics

Live queries end at actual captured server-now. Historical replay and evaluation use the fixed challenge anchor. State (start,end], mode, and filters in outputs.

Store structured issue facts for category/priority/store/product/status analytics. Events provide future response/resolution analysis only when those events actually exist; do not backfill invented historical durations. Returns, receipts, and inventory remain separate evidence streams with explicit source/snapshot scope.

## 10. Planned verification

Rollback/unique constraints, idempotent creation and concurrent retry, migration/backup preservation, private conversation isolation, all-level access matrix, level changes, closed/reopened event consistency, historical seed deduplication, source rebuild survival, and absence of raw PII/tokens. Tests are designed in AUTOMATED_TEST_DESIGN.md, not implemented.
