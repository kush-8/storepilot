# StorePilot — Automated Test Design

Version: 2.2 | Status: backend workflow/API connected and tests green; frontend/evaluation work remains

Current implementation and verified coverage: [Copilot workflow and tests](COPILOT_WORKFLOW_AND_TESTS.md). The detailed design below includes planned requirements; the current report distinguishes implemented behavior from remaining work.


## 1. Objective and execution layers

Verify that StorePilot safely turns employee issues into grounded persistent tickets, that dashboard Analytics answers only within the permitted scope, and that login/JWT and lifecycle rules match [backend/openapi.json](../backend/openapi.json).

| Layer | Planned tooling | Main boundary |
| --- | --- | --- |
| Pure rules/schemas | pytest | Sanitization, routing decisions, validation, priorities, time/filter rules |
| Repositories and persistence | pytest + temporary SQLite | Real joins, scope, transactions, idempotency, lifecycle and source preservation |
| HTTP contract/integration | pytest + httpx ASGI transport; OpenAPI-aware schema validation | Real FastAPI dependencies with deterministic model/retrieval doubles |
| Frontend component/flow | React test tooling chosen during implementation | Chat states, draft/receipt, errors and identity changes |
| Browser E2E | Playwright | Login, follow-up, save, dashboard visibility and analytics drill-down |
| Retrieval/model evaluation | Backend CLI + recorded fixtures and separate real-model runs | Chroma relevance, citations, grounded behaviour and public challenge outputs |
| Deployment smoke | Compose smoke suite when packaging exists | Startup, health, private services, app/vector persistence |

These are the designed layers. Backend agent/workflow/API tests and browser integration checks are implemented and run. Evaluation remains planned; deployment results are recorded in the [Docker and integration guide](DOCKER_AND_INTEGRATION.md). See the current report for exact results.

## 2. Deterministic fixture design

Use temporary independent retail.db and storepilot.db per test. Never mutate the supplied database or restore removed operational CSV files. Freeze a controllable clock and inject model/retrieval adapters.

Employee fixtures: E9001/ST001/level 1; E9002/ST002/level 2; E9003/ST003/level 3; E9004/ST004/level 4. Each creator has two tickets: one Open P2 and one Closed P3. Add separate fixtures for hidden P1, missing creator, revoked session, level change, safety incidents and ambiguous SKU names.

Expected visible totals in the basic fixture are 2, 4, 6 and 8 for viewers 1–4; unresolved totals 1, 2, 3 and 4. Store filters narrow these counts. Put distinctive sentinel text in hidden tickets to detect leakage in data, model inputs and response text.

Keep fixed historical anchor and actual live clock as separate fixture inputs. Source-only expected baseline: 544 cases created by anchor, 407 unresolved, and 21 unresolved P1/P2 in the last 24 hours. These are unscoped evaluation baseline counts; employee-mode expected counts must be independently filtered, never reuse unrestricted values.

## 3. Authentication and JWT cases

| ID | Given / action | Expected |
| --- | --- | --- |
| AUTH-01 | Existing employee and exact assigned store | Token/profile issued; claims and 30-minute expiry correct |
| AUTH-02 | Wrong store, nonexistent employee or nonexistent store | Same generic 401 shape; no enumeration details |
| AUTH-03 | Empty/malformed input or extra role/level fields | 422; no token |
| AUTH-04 | Missing token or token with changed signature | 401; no protected query executed |
| AUTH-05 | Expired token, wrong iss/aud, future iat beyond allowed skew | 401 |
| AUTH-06 | alg=none or unexpected algorithm | Rejected; never select verifier from untrusted header |
| AUTH-07 | Logout then replay same token | 401; session remains revoked |
| AUTH-08 | Employee reassigned to another store | Prior session rejected; correct new pair can log in |
| AUTH-09 | Employee level changes while JWT remains otherwise valid | Next request uses new current level; token/browser level cannot override |
| AUTH-10 | Repeated invalid login/rate threshold | 429 and Retry-After; no raw token/input in logs |

IDs/store are not secret credentials; tests prove pair-validation/token behaviour, not proof of human identity. Test expiry boundaries and clock skew explicitly.

## 4. Authorization matrix and non-leakage

Parameterize all 16 viewer/creator combinations:

| Viewer level | Creator 1 | Creator 2 | Creator 3 | Creator 4 |
| --- | --- | --- | --- | --- |
| 1 | Allow | Deny | Deny | Deny |
| 2 | Allow | Allow | Deny | Deny |
| 3 | Allow | Allow | Allow | Deny |
| 4 | Allow | Allow | Allow | Allow |

Apply the matrix separately to list rows/total, direct detail, dashboard counts/charts, search, Analytics results/model context, related-ticket evidence, and drill-down. Denial must precede aggregation and pagination.

Additional cases:
- Unknown/missing creator/viewer level fails closed.
- Nonexistent and hidden IDs yield the same 404 contract; no hidden title/count/existence hints.
- Changing store/SKU/date/priority filters never broadens scope.
- Hidden rows do not affect visible total, trend, ranking, snippet, citation or source-record list.
- Direct source support-case query applies the same current-level join.
- Level-4 -> level-1 change invalidates cached Analytics/detail output.
- Stored related evidence whose access changed is suppressed/revalidated.
- Conversation/messages/drafts/analytics threads are owner-only, even when a generated ticket is visible.
- Seeing a peer's ticket permits read but not status mutation; visible forbidden update is 403, hidden update 404.
- Client-supplied creator/level/priority overrides fail validation and never alter query authority.

Assert both returned values and the actual repository/model evidence: checking only the UI is insufficient.

## 5. Guardrails, router and multi-turn cases

| ID | Scenario | Expected |
| --- | --- | --- |
| GR-01 | Phone/email/full card/secret in first message | Mask/redact before model, log, state, draft and ticket |
| GR-02 | Safe first turn followed by sensitive/malicious follow-up | Guardrails re-run; unsafe second turn cannot inherit a safe pass |
| GR-03 | Prompt injection requesting restricted data | Safe refusal/security route; no ordinary Data/RAG execution |
| GR-04 | Instruction embedded in retrieved policy/data text | Treated as evidence, never tool/system authority |
| GR-05 | Output contains invented citation or leaked sensitive value | Final validator rejects/returns safe review result |
| RT-01 | Routine policy/POS guidance | RAG route and resolvable supporting sections |
| RT-02 | Pure dashboard ticket-count question | Data route through Analytics with visibility predicate |
| RT-03 | Stock-out cause with inventory/receipts context | Both route; policy and SQL evidence influence answer |
| RT-04 | “Card reader not working” without impact scope | Focused one/several/all follow-up; no invented outage |
| RT-05 | Follow-up confirms all registers cannot take cards | P1 immediate guidance; draft uses collected safe facts |
| RT-06 | Analytics question submitted in Copilot | Dashboard redirect; no incident ticket auto-created |
| RT-07 | Unanswerable/unsupported question | Supported alternatives/uncertainty; no fabricated query |
| RT-08 | Model proposes Data-only for operational policy steps | Validator requires RAG evidence before grounded steps |

Record bounded node handoffs, not hidden model reasoning. All model fixtures accept sanitized typed inputs and return deterministic outputs so rules, not randomness, are tested.

## 6. Grounding, policies and source-data cases

- All five policy documents index with valid headings, stable IDs/source hashes, and consistent indexing/query embedding configuration.
- Retrieval budget <=4 sections; exact required sections for POS outage, returns approval, stock-out, quality/safety and PII rules.
- No public expected labels, conversations, raw PII, or root_cause_hint in retrieval/classifier evidence.
- Citation exists AND supports the claim; reject merely present but irrelevant sources.
- Safety/injury/unsafe demo equipment -> P1, even when historical labels disagree.
- Restricted-data records labelled P3/P4 do not weaken new P1 guardrails.
- Confidence 0.59 triggers review; 0.60 alone does not, while other review triggers still apply.
- Refund >=5000 and no-receipt amount >=1000 require approval; every no-receipt return requires review.
- Missing inventory row remains unknown, not zero.
- ST002 bat investigation uses 0 on-hand/4 system and receipts 18/50 + 20/45; neutral causal wording.
- ST005 tennis investigation checks zero at both store and warehouse.
- Receipt vendor/current product vendor mismatch is preserved, not silently replaced.
- Quality requests/ordinary returns are not automatically counted as unique product defects.
- Policy conflict and insufficient evidence produce review/limitations, not unsupported certainty.

## 7. Ticket persistence and lifecycle cases

| ID | Action | Assertions |
| --- | --- | --- |
| DB-01 | Generate valid owner draft | Ticket/steps/citations/evidence/event/receipt committed; creator from JWT |
| DB-02 | Same key and identical request retried | Same ticket ID, no duplicate child rows, replay response |
| DB-03 | Same key with different draft/revision | 409, original ticket unchanged |
| DB-04 | Concurrent same-key requests | Exactly one ticket; both receive consistent committed receipt |
| DB-05 | Same draft/revision under another key | No second ticket; documented conflict |
| DB-06 | Failure during child insert | Full rollback; no partial ticket/success response |
| DB-07 | Expired/stale/non-owned/unsafe draft | Reject before write; no details leaked |
| DB-08 | Material issue edit | New sanitized turn and reanalysis; old draft cannot silently save altered facts |
| DB-09 | Creator status transition with expected version | Status/event/version/closed timestamp updated atomically |
| DB-10 | Concurrent/stale version or same-state transition | 409; no extra lifecycle event |
| DB-11 | Reopen Closed ticket without reason | Reject; with reason sanitize and record |
| DB-12 | Restart/rebuild source import | Application tickets persist; no source mutation |
| DB-13 | Historical seed twice | One ticket per source_case_id; recorded provenance; no invented confidence/closure time |
| DB-14 | Analytics references imported and source cases | No duplicate count of same seeded case |
| DB-15 | Token/PII inspection of app DB and captured logs | No raw sensitive values/bearer tokens |
| DB-16 | Create ticket requiring approval | Ticket saved with pending flag; no refund/claim/notification executed |
| DB-17 | Repeated message client_message_id | Same logical turn; changed reused content conflicts |

## 8. Analytics and time cases

Compare SQL results to independently enumerated fixture rows, rather than computing expected results with the same query template.

- Shared dashboard/list/Analytics filters and current-level scope agree.
- Apply scope before group/count/rank/limit; page size does not alter aggregate total.
- Rolling window excludes start and includes end; future records excluded.
- Live new ticket after challenge anchor is included when within live window.
- Historical mode rejects end after anchor; immutable evaluator result unaffected by app status edits.
- Date-only receipt evidence never invents within-day order/time.
- Unresolved = Open/In Progress, excludes Closed.
- Model SQL instructions/SQL injection remain parameters or unsupported intents, never executable SQL.
- Result cap/truncation explicit; missing results not filled with zeros as success.
- Dashboard follow-up uses owner context and current scope; not another employee's thread.
- Quality signals use defined reasons and separate ticket/return counts with attribution caveat.
- Timeout/unavailable backend returns safe errors, not a guessed answer.

## 9. API contract checks

Validate backend/openapi.json with a full OpenAPI 3.1-aware validator during later CI. Verify path/operation/schema references and examples. Compare implemented responses/errors to the contract; all protected paths require bearer JWT, only health/login are public. Unexpected client fields are rejected where defined.

Cover 200/201/204 success, idempotent 200 replay, 401/403/404/409/422/429/503/504, rate/auth headers and safe error fields. A structured safety refusal is successful processing with result_type=refusal, not an application crash.

Check JSON schemas and runtime semantic conditions together: clarification has a question; generation_allowed reflects validation; refusal cannot expose hidden evidence; totals/rows and time windows agree.

## 10. Frontend/browser journeys

1. Login with pair -> employee context -> two navigation destinations; no frontend Evaluation/Analytics page.
2. Ambiguous issue -> follow-up -> answer -> steps/draft -> Generate ticket -> receipt -> Dashboard visible row.
3. Save failure/retry does not show premature success or create duplicate tickets.
4. Level-1 session cannot see level-4 ticket through navigation, cached results or direct URL.
5. Ask Analytics on Dashboard -> authorized table -> click permitted ticket detail.
6. Logout/expiry clears private data; next employee never sees prior conversation/detail.
7. PII response displays sanitized content, not raw history.
8. Keyboard/mobile 360 px/loading/empty/error states; labels, focus and priority text remain usable.
9. No raw model HTML execution, secrets in bundle, token in localStorage, or logging sensitive form values.

Use deterministic backend fixtures for browser tests; do not require paid live model calls to test UI states.

## 11. Backend-only RAG and pipeline evaluation

Use all 11 public prompts as held-out evaluation inputs. Compare expected answers only after the same inference graph runs. Execute in no-write mode against isolated source fixtures; assert zero application tickets/events created.

Measure category/priority accuracy (>=75%), citation presence (>=85%) with relevance/validity separately, public safety checks (100%), and data-use correctness (>=75%). Report exact denominators and per-case failures. Add retrieval hit/rank/support measures against manually defined relevant sections; do not equate vector similarity with confidence.

Run deterministic mocked pipeline regressions on every change. Run actual Chroma index and real-model evaluation in a separate configured suite with bounded time/cost, source hashes and model/embedding settings captured. Repeated model variation is reported, not hidden by rerunning until passing. Save actual predictions/metrics/failures only after execution.

## 12. Proposed CI stages and release evidence

Future fast lane: contract/schema checks -> pure rules -> SQLite repository tests -> HTTP integration -> frontend lint/build and deterministic E2E. Separate retrieval/real-model evaluation lane. Deployment smoke after Docker packaging.

Highest-priority blocking failures: identity/authorization leakage, raw PII/token persistence, guardrail bypass, duplicate/partial ticket writes, incorrect time/aggregate scope, and invalid grounding. Capture sanitized failures/configuration, not raw sensitive prompts. No existing suite has been run or certified by this design document.
