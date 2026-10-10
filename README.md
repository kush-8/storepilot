# StorePilot

Planning documents and two independent application codebases for the HCLTech hackathon.

Agreed target stack: React/Vite frontend; Python/uv/FastAPI backend; LangGraph orchestration; Chroma policy vector retrieval; SQLite retail data; Docker Compose packaging. The documents reflect this selection. Dependency migration and container configuration await implementation.

## Current implementation

- `frontend/`: React + TypeScript starter generated with Vite; product screens are not implemented.
- `backend/`: Python + uv + FastAPI; read-only health and dashboard endpoints.
- `backend/database/retail.db`: SQLite database containing all 2,970 source rows from the nine retail CSVs.
- `backend/scripts/`: atomic CSV import and full source-to-database verification.
- `backend/knowledge_base/`: supplied policy documents; original guides refer to their package location as `knowledge_base/`.
- `docs/`: product requirements, app flow, technology decisions, engineering requirements, system design, and frontend design.

Target product: Dashboard combines ticket overview and Analytics; Copilot is a chatbot for reporting issues, asking follow-ups, recommending steps, and generating persistent tickets. Ticket access uses creator current level <= viewer current level. Requested login validates Employee ID + Store ID and issues JWT. Evaluation is backend-only.

Login/JWT, employee authorization, product screens, LangGraph agents, writable ticket storage, Analytics, evaluation runner, and executable automated tests are specified but not implemented. Implementation remains paused. The existing starter dashboard is unscoped and does not implement the revised employee-access contract.

## Directory layout

```text
frontend/                  React/Vite scaffold
backend/                   FastAPI scaffold, database, scripts, policies, tests
data/                      Original business CSVs
evaluation/                Backend evaluation inputs
docs/                      Product, design, API, and test planning documents
.tools/                    Local uv executable used on this workstation
Participant_Guide.md       Original challenge guide
Student_Printable_Guide.*  Original printable HTML/PDF guides
```

Download caches and obsolete root script bytecode have been removed. The backend virtual environment and local uv tool are retained. Source datasets, guides, policy files, database, and application scaffolds are preserved.

## Documents

| Document | Purpose |
|---|---|
| [Product requirements](docs/PRD.md) | Users, scope, must-have features, acceptance criteria, metrics, and deliverables |
| [App flow](docs/APP_FLOW.md) | Navigation, triage/analytics journeys, escalation, and failure states |
| [Technology stack](docs/TECH_STACK.md) | React/Vite and Python/uv/FastAPI decisions, dependencies, and local setup |
| [Engineering requirements](docs/REQUIREMENTS.md) | API contracts, safety rules, data access, evaluation, and implementation checklist |
| [System design](docs/SYSTEM_DESIGN.md) | Agent orchestration, retrieval, SQL schema, query examples, and trust boundaries |
| [Frontend design](docs/FRONTEND_DESIGN.md) | Screen layouts, reusable components, visual tokens, interaction, and accessibility |
| [Ticket data model](docs/TICKET_DATA_MODEL.md) | Durable tickets, private chat/drafts, evidence, events, JWT metadata, and transaction boundaries |
| [OpenAPI contract](backend/openapi.json) | Proposed 16-operation API with schemas, JWT protection, errors, and scope rules |
| [OpenAPI summary](docs/API_CONTRACT.md) | Plain-English endpoints, login, chat-to-ticket, dashboard Analytics and contract notes |
| [Automated test design](docs/AUTOMATED_TEST_DESIGN.md) | Planned rule, database/API, contract, frontend, deployment, and RAG evaluation suites |
| [Data analysis](docs/DATA_ANALYSIS.md) | Findings and limitations across all supplied retail datasets |

## Run the backend

Requires Python 3.12 and uv. If uv is not on PATH, the project-local executable installed during setup is `../.tools/bin/uv.exe` when working inside `backend/`.

```powershell
cd backend
uv sync --locked
uv run python scripts/verify_database.py
uv run uvicorn app.main:app --reload --host 127.0.0.1 --port 8000
```

API documentation: <http://127.0.0.1:8000/docs>. Health: <http://127.0.0.1:8000/api/health>.

For the future model integration, copy `backend/.env.example` to `backend/.env` and supply your own model and API key. Current endpoints do not require model access.

## Run the frontend

Requires Node.js 22.12+ and npm. Use a second terminal:

```powershell
cd frontend
npm install
npm run dev
```

Open <http://localhost:5173> after installing dependencies. The planned Vite `/api` proxy and product screens are documented but not yet configured. Neither API keys nor the database belong in the frontend.

The first frontend dependency install was stopped for document review, so its lockfile is pending. After generating and committing `package-lock.json`, use `npm ci` for subsequent setup.

## Rebuild the SQL database

The original CSV files remain unchanged in `data/`. Evaluation CSVs remain separate from the operational database.

```powershell
cd backend
uv run python scripts/import_csv.py --replace
uv run python scripts/verify_database.py
```

Stop the backend before replacing its database. `--replace` intentionally rebuilds only the source-data snapshot. Proposed application tickets will use a separate writable `storepilot.db`; that database and migrations are not implemented yet.

Without uv or installed dependencies, these two scripts also work with plain Python 3.12 because they use only the standard library.

## Check the scaffold

```powershell
cd backend
uv run pytest
uv run ruff check app scripts tests
```

```powershell
cd frontend
npm run lint
npm run build
```

The backend dashboard uses the event anchor `2026-10-10T12:00:00+05:30`, not the machine clock. Its distributions cover unresolved historical cases at or before that anchor. Import verification passed; full backend/frontend checks remain pending.
