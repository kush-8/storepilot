# StorePilot Backend

FastAPI implementation of the 16 operations in `openapi.json` (the file referred to as
`openai.json`). Login, private chat, sanitized history, policy citations, server-held drafts,
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

## Copilot behavior and limits

The current Copilot uses **local deterministic rules and lexical policy retrieval**, not an OpenAI
model or autonomous multi-agent runtime. `OPENAI_API_KEY`, `OPENAI_MODEL` and model timeout settings
are reserved for a future model adapter and currently unused. Health `chat=ready` means this local
Copilot is available. No paid API key is needed to test this implementation.

The pipeline masks common emails, phone/card numbers and labeled secrets before persistence,
checks common injection/restricted-data patterns, retrieves Markdown policy sections with hashes,
classifies common issue categories and returns recommendations, clarification or refusal. Structured
SKU context enables inventory evidence. Follow-ups reuse sanitized recent conversation context.
These regex/rule safeguards are bounded prototype behavior, not comprehensive PII detection or
an evaluated production classifier. Ambiguous payment scope asks a follow-up rather than saving a draft.

Policy instructions are retrieved as data. Recommendations cite actual policy sections; root cause
is not claimed as confirmed. Tickets may require human review/approval. Saving a ticket records a
report; it does not contact teams, approve refunds, submit claims, change inventory or assign people.
Junior/senior employee visibility is implemented; external escalation queues are not integrated.

Analytics supports authorized ticket counts grouped by store, priority or category, with unresolved
and explicit P1–P4 selection. Use structured filters for time ranges, status, SKU and store. Other
questions return `unsupported`. Arbitrary SQL and unrestricted data exports are not available.

## Postman

See `postman/README.md`. Import both JSON files there and run the collection in order. It includes
all 16 operations plus historical dashboard, retry and revoked-session checks, automatically saves
the bearer token and generated IDs, and creates a fresh issue each run.

## Verification

```powershell
uv run pytest -q
uv run ruff check app scripts tests
```

API tests validate returned objects against the supplied JSON schemas and exercise authentication,
private ownership, level visibility, source immutability, PII masking, clarification/refusal,
filters, status events, rate limiting and concurrent idempotent creation. Tests isolate app state
in temporary files. Importer tests require the original `../data` package and are explicitly skipped
if it is absent. The existing source CSV verifier also requires that package.

Regenerate Postman artifacts after changing the workflow:

```powershell
uv run python scripts/generate_postman.py
```
