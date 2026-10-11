# StorePilot — Technology Stack and Setup

Status: backend agents/API implemented; frontend integrated and Docker Compose supplied; backend evaluation runner implemented, with live quality results recorded separately.

## Architecture and dependencies

Two independent codebases share the maintained [OpenAPI contract](../backend/openapi.json).

| Technology | Current use |
| --- | --- |
| React + Vite | JavaScript/JSX frontend; CSS, Lucide icons and Recharts; npm lockfile |
| Python 3.12/3.13 + uv | Backend runtime and locked dependency management |
| FastAPI + Uvicorn + Pydantic | HTTP endpoints and typed request/agent contracts |
| LangGraph | PII -> Safety -> Triage -> Router -> RAG/Data/Both -> validated response |
| LangChain Core/Groq/Chroma/text splitters | Structured model stages, policy loading, retrieval and grounded generation |
| Groq | Existing generation provider; configured only in the backend |
| Chroma + local ONNX MiniLM | Persistent policy vectors, bounded retrieval and source provenance |
| SQLite + sqlglot | Read-only operational SQL with AST restrictions; transactional application state |
| HS256 JWT with Python standard library | Exact employee/store login, 30-minute tokens, persisted revocation and directory revalidation |
| pytest + httpx + JSON Schema/OpenAPI validators | Offline graph, RAG, guards, real API/auth/storage and contract verification |
| Ruff / Oxlint | Backend and frontend static checks |
| Docker + Docker Compose | Separate frontend/backend images and root Compose with persistent SQLite/Chroma volumes |

Backend dependencies are declared in `backend/pyproject.toml` and pinned by `backend/uv.lock`.
Test validators belong to its `dev` group; no separate test requirements file is needed.
The direct OpenAI/scikit-learn dependencies from the earlier scaffold are no longer required.
Frontend dependencies use `frontend/package.json` and `frontend/package-lock.json`.
Browser tests have their own package and lockfile under `frontend/tests/`.

## Storage and agent responsibilities

| Store | Contents and boundary |
| --- | --- |
| `backend/database/retail.db` | Nine operational tables, 2,970 records and import provenance; read-only at runtime |
| `backend/database/storepilot.db` | Sessions, structured JSON records for private chats/drafts/tickets/events, retry receipts and rate counters; initialized by the runtime |
| `backend/.cache/chroma` | Derived policy index; source Markdown remains authoritative |
| `backend/.cache/embeddings` | Downloaded local ONNX embedding weights |
| `backend/evaluation/` | Public prompts, prediction schema and backend-only workflow evaluation runner |

The removed operational CSVs are unnecessary. Verification uses SQLite integrity, foreign keys,
manifest row counts and seeded observations; it cannot recompute hashes from absent CSV contents.
The proposed normalized application schema is retained in
[TICKET_DATA_MODEL.md](TICKET_DATA_MODEL.md); the current runtime uses structured JSON records.

The same DataAgent handles operational evidence and dashboard ticket-count questions.
Operational queries pass a read-only SQL tool with table/column/function allowlists, named
parameters, row/execution caps, mandatory dates and case visibility. Analytics receives the full
already-authorized ticket set and computes bounded counts/groups deterministically; only the
sanitized question goes to its planning model.

Policy RAG loads Markdown, chunks by headings, retrieves local Chroma vectors and validates
citation IDs and model output. Safety/PII guardrails run before routing and validate generated
content. APIs verify current policy hashes, refund/priority rules, draft eligibility and ownership.

## Local setup

From `backend/`:

```powershell
uv sync --locked
Copy-Item .env.example .env
uv run python scripts/verify_database.py
uv run python -m app.agents.rag index
uv run uvicorn app.main:app --reload --host 127.0.0.1 --port 8000
uv run pytest -q
uv run ruff check app scripts tests
```

Copy the example only for a new configuration. Set `GROQ_API_KEY` and a persistent `JWT_SECRET`
in ignored `backend/.env`. `DATABASE_PATH` and `APPLICATION_DATABASE_PATH` select separate
SQLite files. See `.env.example` for actual model/retrieval settings. Indexing downloads local
embedding weights on first use. Readiness checks configured resources; it does not certify live
provider availability. Permitted model requests return unavailable without model setup.

From `frontend/`:

```powershell
npm ci
npm run dev
npm run lint
npm run build
```

Vite serves port 5173 and proxies `/api` to `127.0.0.1:8000`. The active login, Copilot, ticket and dashboard/analytics screens call the real backend. The target navigation remains
Dashboard (overview plus Analytics) and chat Copilot, with login and ticket detail utilities.
Evaluation stays in backend tests/CLI. UI implementation uses JavaScript today; TypeScript remains
a possible frontend migration rather than an installed application requirement.

The workstation-local uv executable is `../.tools/bin/uv.exe` from either codebase directory.
That ignored tool folder is not a portable dependency; other machines need their own uv setup.

## Configuration and deployment plan

Keep provider keys, JWT signing secrets and SQLite files in the backend. The frontend stores
tokens in local storage when Remember Me is selected and session storage otherwise;
request authorization uses current directory levels. Historical data uses the supplied
noon IST anchor on 10 October 2026; live tickets use server UTC timestamps and `(start,end]` filters.

Docker packaging uses `frontend/Dockerfile`, `backend/Dockerfile`, per-codebase `.dockerignore`
files and root `compose.yaml`. Nginx proxies `/api` to FastAPI; SQLite application records and
local Chroma/embeddings use named volumes. The source snapshot is mounted read-only. Startup
checks persistent signing configuration and prepares the policy index. Run `docker compose up --build`
from the root; see [Docker and integration guide](DOCKER_AND_INTEGRATION.md).

See the [current workflow and verification report](COPILOT_WORKFLOW_AND_TESTS.md) for all endpoints,
test results and live verification limits. Update lockfiles deliberately and rerun relevant checks.
