# StorePilot — Technology Stack and Setup

Status: agreed technology direction; dependency and container changes await implementation.

## 1. Chosen architecture

Two independent codebases share an HTTP contract:

- `frontend/`: React + TypeScript built with Vite; npm dependency management.
- `backend/`: Python 3.12 + FastAPI; uv dependency management.
- Agent orchestration: LangGraph with typed state and conditional routing.
- Vector database: Chroma for policy documents, embeddings, and citation metadata.
- Source operational data: read-only SQLite `retail.db` under `backend/database/`.
- Application data: separate writable SQLite `storepilot.db` for tickets, private conversations, drafts, JWT session metadata, and audit events.
- Packaging and local deployment: Docker images and Docker Compose.

React is the UI layer. FastAPI provides the backend.

## 2. Backend choices

| Technology | Use | Decision |
|---|---|---|
| Python 3.12 | Application and data processing | Standard library covers CSV, SQLite, hashing, dates, and JSON |
| uv | Environment, dependency resolution, and execution | `pyproject.toml` declares dependencies; `uv.lock` pins resolution |
| FastAPI + Uvicorn | Typed HTTP API and local server | OpenAPI supports contract inspection from the frontend |
| Pydantic | Request, response, and agent result validation | Reject invalid categories, confidence values, and output shapes |
| sqlite3 | Source and application databases | Immutable source connections; deterministic transactional ticket writes; employee-scoped agent reads |
| LangGraph | Cooperating agent workflow | PII -> Safety -> Router -> RAG/Data/Both; dashboard Analytics and validated ticket handoff |
| Chroma (`chromadb`) | Vector search over policy sections | Persistent policy collection with embeddings, document text, and citation metadata |
| OpenAI Python SDK | Planned model adapter | Structured output through a configured compatible model; no hardcoded model choice |
| python-dotenv | Local backend configuration | Credentials remain in ignored backend `.env` |
| JWT implementation (library selected later) | Requested Employee ID + Store ID login | Signed short-lived token, server session/revocation checks, current directory/level lookup; no implementation yet |
| pytest + httpx | Backend behavior and API tests | Verify importer safety and actual API/data integration |
| Ruff | Python lint checks | Keep source consistent without a separate formatting stack |
| Docker + Docker Compose | Repeatable application packaging | Separate frontend, backend, and Chroma services; persistent data mounts |

LangGraph workflows, Chroma retrieval, model integration, and Docker packaging are planned. The current backend manifest/lockfile still describe the earlier scaffold; when implementation resumes, add `langgraph` and `chromadb`, remove the direct `scikit-learn` dependency, and regenerate `uv.lock`. The model SDK remains behind a backend adapter. Model credentials are unnecessary for importing data or viewing the initial dashboard. Structured schemas constrain output format, but grounding and business-rule correctness require separate validation.

### Storage responsibilities

| Store | Contents | Access |
|---|---|---|
| Chroma | Policy section embeddings, text, source IDs, headings, slugs, hashes | Backend retrieval agent and controlled indexing job |
| SQLite retail.db | Retail source tables and import provenance | Read-only source queries; related support cases also enforce employee scope |
| SQLite storepilot.db | Tickets, conversations/drafts, evidence/events, idempotency and JWT session metadata | Ticket service transactions; authorized read-only Data/Analytics tools |
| Local artifacts | Backend-only evaluation outputs | Controlled evaluator; no frontend evaluation endpoint |

CSV records remain in SQLite. Do not embed entire operational tables or public expected answers into the policy collection. Chroma is a derived retrieval index; source Markdown remains authoritative.

## 3. Frontend choices

| Technology | Use |
|---|---|
| React | Reusable screen and evidence components |
| TypeScript | API types, state, and component props |
| Vite | Dev server, API proxy, and production build |
| Native fetch | API client with explicit loading/error states and cancellation |
| CSS variables and plain CSS | Shared design tokens and responsive layouts |
| Oxlint | Static frontend checks supplied by the generated Vite template |

The scaffold avoids adding a router or state library before multiple screens need them. Use accessible HTML/CSS bars for initial distributions; larger analytical charts can be added later with an accompanying table.

StorePilot has Dashboard and chat Copilot pages, plus a login utility view. Dashboard combines overview and Analytics. Copilot reports issues, asks follow-ups, recommends steps and generates persistent tickets. Evaluation stays in backend tests/CLI.

## 4. Repository ownership

```text
frontend/                  # npm project, UI source; lockfile after initial install
backend/                   # uv project, API, scripts, tests, SQL database
docs/                      # shared product/engineering documentation
data/                      # immutable input CSV files
backend/knowledge_base/    # immutable source policies (current location)
evaluation/                # public cases and prediction schema
```

Each codebase installs, tests, and builds independently. The backend reads the supplied inputs by paths derived from its own location; API data never depends on the frontend working directory.

Planned deployment files: `frontend/Dockerfile`, `backend/Dockerfile`, per-codebase `.dockerignore`, and root `compose.yaml`. They have not been created.

## 5. Local commands

Python requires `>=3.12,<3.14`; `.python-version` selects 3.12. Use Node.js 22.12+ for the generated Vite template.

```powershell
cd backend
uv sync --locked
uv run python scripts/verify_database.py
uv run uvicorn app.main:app --reload --host 127.0.0.1 --port 8000
```

```powershell
cd frontend
npm install
npm run dev
```

If uv is not installed on PATH on this workstation, `../.tools/bin/uv.exe` is available from either codebase directory. That local tool directory is ignored and is not a portable project dependency; other machines should install uv normally.

## 6. Configuration and deployment boundary

Backend `.env` currently holds `DATABASE_PATH`, `OPENAI_API_KEY`, and `OPENAI_MODEL`. Planned settings add `APPLICATION_DATABASE_PATH`, backend-only `JWT_SIGNING_KEY`, JWT issuer/audience/expiry, and source/application data modes. Requested login validates Employee ID + assigned Store ID and issues JWT; neither login nor token code is implemented.

The fixed anchor applies to historical challenge replay and backend evaluation. Live application tickets use actual server UTC timestamps and captured server-now windows. IDs/store IDs are not secrets; the requested prototype pair lookup establishes directory context. Frontend retains bearer JWT only in memory; current levels always come from the server directory.

Planned settings also include `CHROMA_HOST`, `CHROMA_PORT`, `CHROMA_COLLECTION`, and an explicit embedding model/version. Use `CHROMA_HOST=localhost` for a host backend and `CHROMA_HOST=chroma` inside Compose. Keep the same embedding model, dimensions, and normalization for policy indexing and queries; record that configuration with index/evaluation artifacts. Choose and pin the embedding implementation before indexing. Provision any model weights during setup so first-request downloads do not disrupt the demo.

Planned development setup uses Vite's `/api` proxy to `127.0.0.1:8000`; that proxy is not configured yet. For deployment, serve the built frontend and proxy `/api` to FastAPI on the same origin. A split-origin deployment would require an explicit CORS allowlist. Never place credentials in a `VITE_*` variable, browser storage, or a frontend bundle.

### Docker Compose plan

- `frontend`: build React with Vite; serve static assets through a web server that proxies `/api` to `backend:8000`.
- `backend`: Python image with uv-managed dependencies; run FastAPI via Uvicorn; read the SQLite snapshot and policy source files from read-only mounts; mount writable application DB directory separately, including SQLite journal files.
- `chroma`: private vector-database service, reached by the backend HTTP client; persist index data in a named volume.
- Run policy indexing as a deliberate setup job after Chroma is ready. It must not silently rewrite the collection on every API startup.
- Pin container versions when implementation begins. Compose must preserve application tickets/conversations, vector data, and evaluation artifacts across container recreation. Source rebuild and application migration are separate operations.
- Publish only the frontend port for the packaged demo; expose backend/Chroma host ports only in a local development configuration.

The future packaged startup command is `docker compose up --build`. It will become runnable after the Dockerfiles, service health checks, proxy, mounts, and indexing job are implemented. LangGraph runs inside FastAPI; it is not a separate service.

## 7. Dependency discipline

The backend lockfile exists. Frontend dependency installation was stopped for document review; generate its `package-lock.json` with the initial `npm install` when implementation resumes. Commit both lockfiles, then use `npm ci` and `uv sync --locked` for repeatable setup. Declared version ranges are compatibility bounds, not a claim that they are the newest packages. Update lockfiles deliberately and rerun relevant checks after dependency changes.

## 8. Official references

- [React: building from scratch](https://react.dev/learn/build-a-react-app-from-scratch)
- [Vite: setup and React templates](https://vite.dev/guide/)
- [FastAPI: application setup](https://fastapi.tiangolo.com/tutorial/first-steps/)
- [uv: project configuration](https://docs.astral.sh/uv/concepts/projects/config/)
- [Pydantic validation](https://docs.pydantic.dev/latest/)
- [LangGraph overview and stateful orchestration](https://docs.langchain.com/oss/python/langgraph/overview)
- [Chroma collections and vector retrieval](https://docs.trychroma.com/docs/overview/getting-started)
- [Chroma client-server connection](https://docs.trychroma.com/docs/run-chroma/client-server)
- [Docker Compose application model](https://docs.docker.com/compose/intro/compose-application-model/)
- [OpenAI: structured model outputs](https://developers.openai.com/api/docs/guides/structured-outputs?api-mode=responses)
