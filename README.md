# StorePilot

Retail issue reporting and ticket analytics, with separate React/Vite and Python/uv/FastAPI codebases.
The backend connects PII and Safety guardrails, Triage, Router, policy RAG and a shared
Data/Analytics agent through LangGraph. Chroma holds policy vectors; SQLite holds operational
source data and durable application records. Docker Compose packages and starts both services.

## Current state

- Backend: all 16 contracted operations, JWT sessions, private conversations, validated drafts,
  transactional ticket creation, lifecycle events, current-level visibility and dashboard analytics.
- Frontend: React screens call the real backend for login, chat, ticket saving/status, dashboard
  and analytics. Vite proxies development requests; Nginx proxies the Docker deployment.
- Operational source: `backend/database/retail.db`, nine tables and 2,970 rows. The removed
  operational CSVs are no longer required. Source queries are read-only.
- Application state: separate `backend/database/storepilot.db`, initialized by the backend.
- Verification: **338 backend tests**, six browser fixture journeys and six actual-API browser
  journeys pass. The backend evaluator runs the 11 public cases and records live model quality separately.

The intended UI has Dashboard with integrated Analytics and a chat Copilot for follow-ups,
recommended steps and explicit ticket saving. Ticket reads require the creator's current numeric
escalation level to be less than or equal to the viewer's current level. Conversations and drafts
remain private. Evaluation has no frontend page or public API endpoint.

## Layout

```text
frontend/                  React/Vite UI, npm lockfile and browser test package
backend/app/               FastAPI, storage/services and independent agent modules
backend/database/          Operational snapshot and writable application database
backend/scripts/           SQLite verification and Postman collection generation
backend/knowledge_base/    Policy Markdown sources
backend/evaluation/        Public cases, submission schema and backend workflow evaluator
backend/tests/             Offline workflow, RAG, guardrail, API, auth and contract tests
docs/                      Product, design, flow, contract and verification documents
.tools/                    Ignored workstation-local uv executable
```

## Documents

| Document | Purpose |
| --- | --- |
| [Product requirements](docs/PRD.md) | Product scope and acceptance criteria |
| [App flow](docs/APP_FLOW.md) | Intended navigation and employee journeys |
| [Technology stack](docs/TECH_STACK.md) | Implemented stack, setup and deployment plan |
| [Engineering requirements](docs/REQUIREMENTS.md) | Safety, access and evaluation requirements |
| [System design](docs/SYSTEM_DESIGN.md) | Architectural design and trust boundaries |
| [Frontend design](docs/FRONTEND_DESIGN.md) | Layout, interactions and accessibility |
| [Ticket data model](docs/TICKET_DATA_MODEL.md) | Proposed normalized storage design |
| [OpenAPI contract](backend/openapi.json) | Exact requests, responses and errors |
| [OpenAPI summary](docs/API_CONTRACT.md) | Plain-English API summary |
| [Workflow, endpoints and tests](docs/COPILOT_WORKFLOW_AND_TESTS.md) | Current implementation, all 16 endpoints, verified coverage and limits |
| [Automated test design](docs/AUTOMATED_TEST_DESIGN.md) | Wider test roadmap, including unfinished evaluation/browser checks |
| [Data analysis](docs/DATA_ANALYSIS.md) | Findings across the supplied datasets |

## Run with Docker

```powershell
docker compose up --build
```

Open <http://localhost:8081>. FastAPI docs are at <http://localhost:8001/docs>.
See [Docker setup and integration checks](docs/DOCKER_AND_INTEGRATION.md) for configuration,
persistence, alternate ports and test results. First startup downloads embeddings and builds the index.

## Run locally

From `backend/`, with Python 3.12 or 3.13 and uv:

```powershell
uv sync --locked
Copy-Item .env.example .env
uv run python scripts/verify_database.py
uv run python -m app.agents.rag index
uv run uvicorn app.main:app --reload --host 127.0.0.1 --port 8000
```

Copy the example only for a new configuration. Set `GROQ_API_KEY` for model stages and
`JWT_SECRET` for persistent signed sessions. Indexing downloads local embedding weights on first
use. Local guards and login remain available without a model key; permitted model requests return
unavailable. API docs: <http://127.0.0.1:8000/docs>.

The workstation-local uv executable is `../.tools/bin/uv.exe` from either codebase directory.

From `frontend/`, in a second terminal:

```powershell
npm ci
npm run dev
```

Vite serves <http://localhost:5173> and proxies `/api` to `127.0.0.1:8000`.
Credentials and databases belong in the backend.

## Verify

```powershell
cd backend
uv run pytest -q
uv run ruff check app scripts tests
uv run python scripts/verify_database.py
```

```powershell
cd frontend
npm run lint
npm run build
```

See [backend tests](backend/tests/README.md) and [browser test plan](frontend/tests/README.md).
Backend tests replace model responses while keeping the real graph, SQL executor, authentication,
API handlers and persistence. They do not certify live model quality or frontend journeys.
