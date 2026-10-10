# StorePilot: connected workflow, API flow and verification

Verified on 10 October 2026. The existing agents are connected to the backend API.
The workflow was tested first before API wiring. After integration and cleanup, the complete
backend suite has **282 passing tests, zero failures**. Ruff passes.

Live Groq generation could not be tested because `GROQ_API_KEY` is not configured.
The local embedding model and Chroma index were built successfully: **28 policy chunks**.
Real vector retrieval returned the POS Card Reader Runbook. Frontend integration remains pending;
its existing mock services were preserved during removal of unused starter assets.

## Issue reporting and ticket flow

```mermaid
sequenceDiagram
    participant Employee
    participant API as FastAPI
    participant Guards as PII and Safety
    participant Graph as Triage and Router
    participant RAG as Policy RAG
    participant Data as Shared DataAgent
    participant DB as Application SQLite
    Employee->>API: Log in with employee ID and assigned store ID
    API-->>Employee: JWT and current employee context
    Employee->>API: Create private conversation, then send issue
    API->>Guards: Sanitize current message and bounded history/context
    alt Restricted or unsafe request
        Guards-->>API: Refuse before any model or data tool
        API-->>Employee: Safe response and escalation information
    else Allowed
        API->>Graph: Sanitized issue, validated context and verified caller ID
        Graph->>Graph: Triage, then choose RAG / Data / Both / clarification
        opt Policy evidence selected
            Graph->>RAG: Focused policy question
            RAG-->>Graph: Grounded statements and validated source citations
        end
        opt Database evidence selected
            Graph->>Data: Bounded evidence plan and trusted caller ID
            Data-->>Graph: Validated read-only SQL evidence
        end
        Graph-->>API: Joined safe result or focused follow-up
        API->>API: Check policy hashes, priorities, confidence and approval rules
        API->>DB: Save sanitized messages and eligible server-held draft
        API-->>Employee: Recommendations, citations, escalation and draft
    end
    Employee->>API: Explicit Generate ticket: draft ID/revision + Idempotency-Key
    API->>DB: Atomically commit ticket, creation event and retry receipt
    API-->>Employee: Ticket ID; repeat save returns the same ticket
    Employee->>API: Dashboard or analytics question
    API->>API: Apply current employee levels and date/other filters
    API->>Data: Analyze authorized tickets with a bounded count/group plan
    Data-->>Employee: Grounded count and grouping results through API
```

Triage precedes Router because the existing Router consumes its structured classification.
PII and Safety always precede both. The Both route runs specialists in parallel and joins once.
The graph and guardrail modules remain independent of FastAPI. `app/services/copilot.py`
adapts graph results to the public ChatTurn/Draft contract; API handlers own persistence.

Follow-ups re-run guards and use recent sanitized user messages. Validated store/SKU selections
take precedence over model extraction. Ambiguous POS impact asks one-register/all-register
clarification. Missing required fields prompt clarification. Urgent injury/equipment risks and
confirmed all-register outages enforce P1 and immediate human escalation.

Policy citations resolve to the same canonical sections served by the policy API and include
current raw-file hashes. Unsupported, invalid, partial, missing-policy, or confidence-below-0.60
results cannot produce validated saveable drafts. No-receipt returns require review; approval
thresholds are INR 5,000 with receipt and INR 1,000 without receipt. Saving a ticket records an
issue; it does not approve refunds, change inventory, notify people or submit claims.

Model calls run outside SQLite write transactions. Before committing a turn, the API rechecks
the conversation version and duplicate-message receipt, preventing concurrent history overwrite.
Later turns invalidate earlier drafts. Draft expiry and version checks still apply at ticket save.

## How the same DataAgent handles analytics

`DataAgent.invoke` plans and executes validated operational SELECT queries against read-only
`retail.db`. SQL table/column/function restrictions, named parameters, row caps and an execution
budget constrain the tool. Historical case visibility and `(start,end]` windows are applied by
the tool even if generated SQL omits them. Receipts use calendar dates. Missing rows do not
establish zero stock.

`DataAgent.analyze` plans ticket counts by store, category, priority or status, with optional
status/priority selection. FastAPI loads and scopes the full matching ticket set first, then
the same agent aggregates it deterministically. The planning model receives the sanitized
question; it does not receive ticket descriptions, creator identities or row contents.

Live mode reads newly persisted ticket records from `storepilot.db`; historical mode reads
imported support cases from `retail.db`. Source data stays read-only, and removed operational
CSV files are not required or restored. Runtime tickets currently use structured JSON records
in SQLite, including steps/citations/evidence/escalation/events. The normalized
table layout in the design document remains a future storage design; obsolete test fixtures
that assumed it were removed.

Scope remains **creator current escalation level <= viewer current escalation level**.
Current directory changes are rechecked per request. Private conversations, drafts and analytics
threads are owner-only. Analytics computes counts before the 200-output-row cap. Time/other
filters resolve into response context so the UI can explain the result scope.

## Every API endpoint

The maintained [OpenAPI document](../backend/openapi.json) contains the exact schemas, validation
limits and status codes. All endpoints except health/login require a bearer JWT.

| Endpoint | What it does and what matters |
| --- | --- |
| `GET /api/health` | Reports source/application database, policy index and configured chat readiness. Missing model setup yields degraded readiness; this does not certify live provider availability. |
| `POST /api/auth/login` | Validates employee ID and exact assigned store ID; returns a signed 30-minute JWT and current employee context. Wrong pair returns 401; rate limit returns 429. |
| `POST /api/auth/logout` | Revokes the current persisted session; returns 204. Later use of that token returns 401. |
| `GET /api/me` | Returns current employee ID, assigned store, role and numeric level from the directory. |
| `GET /api/stores` | Returns store/warehouse choices for the affected issue location. |
| `POST /api/conversations` | Creates an owner-only conversation; affected store defaults to the employee's assignment. Returns 201. |
| `GET /api/conversations/{conversation_id}` | Returns that owner's sanitized history. Other employees receive the same 404 as a missing resource. |
| `POST /api/conversations/{conversation_id}/messages` | Runs the guarded agent workflow on an issue/follow-up; returns clarification, recommendations, refusal, redirect, unsupported or unavailable. `client_message_id` replays the same logical turn; changed content under the same ID returns 409. |
| `GET /api/ticket-drafts/{draft_id}` | Returns the owner's server-held draft, revision and generation eligibility. Stale/expired drafts cannot be committed. |
| `POST /api/tickets` | Accepts only draft ID/revision with `Idempotency-Key`; saves validated draft atomically. First save is 201; same replay is 200; stale/conflicting requests are 409. |
| `GET /api/tickets` | Lists current-level-authorized tickets after mode/date/store/SKU/status/priority/category/search filtering, then paginates. Total reflects the full scoped set. |
| `GET /api/tickets/{ticket_id}` | Returns permitted ticket details, steps, evidence, escalation and lifecycle events. Hidden and missing tickets both return 404. |
| `PATCH /api/tickets/{ticket_id}/status` | Creator-only status change with `expected_version`; updates version and appends an event. Peers can view without gaining mutation permission; reopening requires a reason. Historical cases are immutable. |
| `GET /api/dashboard` | Returns totals, unresolved/P1/P2 workload and store/category/priority distributions for the same authorized filtered set. |
| `POST /api/dashboard/analytics` | Calls the same DataAgent for scoped ticket-count questions. Accepts dashboard filters and an optional private clarification thread; guards run before planning. |
| `GET /api/policies/{section_id}` | Returns the canonical cited policy section, source text and hash; unknown sections return 404. |

Backend evaluation has no public endpoint. The React frontend remains a separate integration task.

## What the automated tests prove

| Suite | Passing tests | Coverage |
| --- | ---: | --- |
| `tests/agents/guardrails` | 76 | PII kinds, Unicode/normalization, identifier preservation, redaction metadata, safety signals, refusal/urgency, and isolated imports. |
| `tests/test_workflow.py` | 36 | Actual compiled graph order, each route, parallel join, focused RAG questions, repeated-call isolation, partial failure, real read-only SQL evidence, current levels, mandatory windows and caps. |
| `tests/test_connected_agents.py` | 26 | Refusal before all external agents, urgent priority, unsafe output/follow-up rejection, provider failures, shared Data/Analytics behavior, SQL escape attempts, refund thresholds and confidence boundaries. |
| `tests/test_rag.py` | 22 | Chunk/source provenance, real temporary Chroma persistence/reopening, stale-index rejection, bounded retrieval, actual generation-chain validation, invalid citations, empty evidence and provider errors. |
| `tests/test_api.py` | 34 | All 16 operations through real FastAPI; graph/model calls, sanitized persistence, clarification/follow-up, draft/save/retry/lifecycle, concurrent ticket saves, current-level access, analytics privacy, missing configuration and honest health; all creator/viewer levels, rollback, expiry, exact date boundaries and lifecycle events. |
| `tests/test_contract.py` | 43 | OpenAPI 3.1 validation, reusable schemas/examples, operation registration/security and authority-field rejection. |
| `tests/test_auth.py` | 35 | Independent JWT signature/claims, exact directory pair, invalid input/token/session cases, protected routes, current directory changes and logout revocation. |
| `tests/test_context_and_policies.py` | 8 | Authenticated employee/location context and source text/hash resolution across all five policies. |
| `tests/test_database.py` | 2 | Read-only database integrity/counts and supplied seeded observations; no operational CSV dependency. |

The offline API fixture replaces structured models and policy retrieval with deterministic
collaborators. It keeps the production graph, RAG validation, SQL executor, authentication,
SQLite transactions, API handlers and response-schema validation real. Tests disable external
network calls and use temporary application databases. Real embeddings/Chroma retrieval were
also checked separately against the built local index. None of this certifies real model answer
quality or backend evaluation scores.

Run the complete suite from `backend`:

```powershell
uv sync --locked
uv run pytest -q
uv run ruff check app scripts tests
uv run python scripts/verify_database.py
```

Result: **282 passed**; Ruff: **all checks passed**. Frontend `npm run lint` completes without
warnings and `npm run build` succeeds after restoring its locked dependencies. These are static/build
checks, not browser journey verification. SQLite verification confirms all nine tables,
2,970 rows, integrity, foreign keys, manifest counts and seeded stock observations.

### Cleanup of the 108 pre-existing failures

Of the 108 earlier failures, 11 authentication/policy cases were migrated to the actual
`JWT_SECRET`/`sessions` runtime. The remaining 97 cases belonged to six obsolete modules
requiring a superseded orchestrator, normalized fixture tables or a missing evaluation runner.
Those modules, unused model/tool doubles, fixture SQL and duplicate test catalogues were removed.
The connected suites cover the implemented workflows; 11 additional API regressions preserve
unique scope, rollback, expiry, date and lifecycle checks against the actual persistence format.
No failures are hidden using skipped or expected-failure markers.

The unused legacy Copilot implementation was removed. Shared message sanitation now lives in
`app/services/messages.py`, used by the API, connected Copilot and historical reporting. CSV import
tooling was retired because the operational source is the retained SQLite snapshot; verification
opens it read-only and does not require removed CSVs. Retained source hashes are provenance, not
recomputed comparisons against absent files. Evaluation remains unfinished, with its inputs and
test design preserved; deleting obsolete evaluator-interface tests does not complete evaluation.

## Live setup and remaining work

Configure `GROQ_API_KEY` in `backend/.env` using `.env.example`; set `JWT_SECRET` for persistent
sessions. The embedding model/index are cached locally and ignored by Git. On a fresh checkout,
build them before chat:

```powershell
uv run python -m app.agents.rag index
uv run uvicorn app.main:app --reload --host 127.0.0.1 --port 8000
```

Next verification requires real Groq prompts/answers, followed by frontend API wiring and browser
journey checks and implementation of backend-only evaluation.
No live provider success, frontend integration or completed evaluation is claimed by this report.
