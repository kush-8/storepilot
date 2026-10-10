# StorePilot Backend

FastAPI implementation of the 16 operations in `openapi.json`. Login, private chat, sanitized history, policy citations, server-held drafts,
transactional ticket creation, status events, scoped dashboard and analytics are implemented.

## Start locally

Python 3.12 or 3.13 is required. From the backend directory:

```powershell
uv sync --locked
Copy-Item .env.example .env
uv run uvicorn app.main:app --reload --host 127.0.0.1 --port 8000
```

On this workstation the installed virtual environment can also be used directly:

```powershell
.\.venv\Scripts\python.exe -m uvicorn app.main:app --reload --host 127.0.0.1 --port 8000
```

Open `http://127.0.0.1:8000/docs` for Swagger or `http://127.0.0.1:8000/openapi.json`
for the served contract. Health is `http://127.0.0.1:8000/api/health`.

Set `JWT_SECRET` in `.env` to a random secret containing at least 32 bytes. Without a configured
secret, development uses a process-local key and restart invalidates all existing tokens.
`APP_ENV=production` requires a configured key. Never share this signing key with Postman or clients.

## Persistence and access

- `DATABASE_PATH=database/retail.db`: immutable retail snapshot, opened with SQLite `mode=ro`.
- `APPLICATION_DATABASE_PATH=database/storepilot.db`: automatically initialized writable state
  with schema version 1, sessions, conversations, drafts, tickets, retry receipts, rate counters
  and analytics threads. Back up this file to preserve application work.
- Prototype login checks an exact employee/store assignment. Employee IDs are not secret credentials.
  Tokens expire after 30 minutes; logout persists revocation. Every request rechecks the directory.
- Ticket reads, searches and aggregates require creator's **current** level <= viewer's current
  level. Conversations, drafts and analytics threads remain owner-only. Only creators change status.
- Duplicate messages are replayed by client UUID. Ticket saves require `Idempotency-Key`; same
  payload/key returns the existing ticket. Conflicts and stale versions return 409. Saves and
  status events commit atomically. A later turn invalidates earlier drafts; drafts expire in 30 minutes.
- Historical snapshot queries read imported cases up to noon IST on 10 October 2026. Historical
  cases retain recorded classification and unknown closure times and cannot be edited. Live mode
  includes newly created application tickets only. No source seeding or double counting occurs.

## Connected Copilot and Analytics

The API now uses the existing LangGraph workflow: PII -> Safety -> Triage -> Router ->
RAG/Data/Both -> validated response and draft. Agents remain separated from HTTP and storage.
RAG uses Chroma with local ONNX embeddings; model stages use the existing Groq configuration.
The same DataAgent provides operational SQL evidence and dashboard ticket-count analytics.

Configure `GROQ_API_KEY` in `.env` and build the policy index before live model use:

```powershell
uv run python -m app.agents.rag index
```

Health reports retrieval/model setup honestly. Guards and login remain available without a model
key; safe issue requests then return unavailable, with no local-rule fallback. Model availability
is configured readiness, not a claim that a live provider request succeeded.

Follow-ups reuse bounded sanitized history. Responses verify current policy hashes and preserve
human review, approval and escalation requirements. Tickets save only after employee confirmation;
partial evidence and confidence below 0.60 do not produce validated saveable drafts. Saving does
not notify teams, approve refunds, submit claims, transfer stock or confirm root cause.

Dashboard Analytics calls the same DataAgent with authorized, date-filtered rows from the runtime
or historical database. Counts are computed over the full matching set before response row limits.
Only the sanitized question reaches the analytics planning model; private issue text and ticket
rows do not. Supported groupings are store, category, priority and status. Other questions clarify
or return unsupported. Current-level visibility and private thread ownership are enforced by API.

See [workflow, endpoint and test report](../docs/COPILOT_WORKFLOW_AND_TESTS.md).
The full cleaned backend suite passes: **282 tests**. Obsolete orchestration/storage fixtures
were removed; authentication and policy checks were migrated to the current runtime.
Live provider quality, frontend journeys and backend evaluation remain separate work.

## Postman

See `postman/README.md`. Import both JSON files there and run the collection in order. It includes
all 16 operations plus historical dashboard, retry and revoked-session checks, automatically saves
the bearer token and generated IDs, and creates a fresh issue each run.

## Verification

```powershell
uv run pytest -q
uv run ruff check app scripts tests
```

The [agent workflow](app/agents/workflow/README.md) explains independent agent boundaries
and standalone CLI usage. The [RAG guide](app/agents/rag/README.md) covers indexing and retrieval.
Verify the retained source database without the removed operational CSVs:

```powershell
uv run python scripts/verify_database.py
```

Verification checks SQLite integrity, foreign keys, row counts against retained import provenance,
hash format and seeded stock observations. It cannot compare removed CSV contents or recompute
their original hashes. The snapshot is opened read-only.

Regenerate the Postman artifacts after intentional API contract changes:

```powershell
uv run python scripts/generate_postman.py
```
