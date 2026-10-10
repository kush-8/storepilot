# StorePilot Backend

Independent Python 3.12 project managed by uv. Dependency declarations are in `pyproject.toml`; resolved dependencies are in `uv.lock`.

```powershell
uv sync --locked
uv run python scripts/verify_database.py
uv run uvicorn app.main:app --reload --port 8000
```

If uv is not on PATH, replace `uv` with `../.tools/bin/uv.exe` on this workstation.

Starter endpoint code exists; full API tests are pending:

- `GET /api/health`: database readiness, row counts, and event anchor; 503 if unavailable.
- `GET /api/dashboard`: case totals plus unresolved priority, category, and region distributions.
- `GET /docs`: generated API documentation.

Database path defaults to `database/retail.db` relative to this directory. Optional settings are documented in `.env.example`. Connections use SQLite read-only mode.

The CSV importer reads the nine operational datasets from `../data`. It enforces typed columns, primary/foreign keys, and constraints; verifies integrity; records source hashes; and publishes the database atomically after successful import. Timestamps are normalized to ISO text interpreted as IST, Yes/No becomes 1/0, and blank cells become NULL. All other text is preserved.

```powershell
uv run python scripts/import_csv.py --replace
uv run python scripts/verify_database.py
uv run pytest
uv run ruff check app scripts tests
```

Standalone LangChain policy RAG with LangGraph orchestration, Groq, and ChromaDB is implemented in
[`app/agents/rag`](app/agents/rag/README.md). It is not connected to any API route.

```powershell
uv run python -m app.agents.rag index
uv run python -m app.agents.rag ask "When does a refund require manager approval?"
```

The index command downloads local embedding weights on first use. The ask command
loads `GROQ_API_KEY` from `backend/.env`. Run offline RAG tests with
`uv run pytest tests/test_rag.py`. Remaining agents and additional API endpoints
are described in `../docs/SYSTEM_DESIGN.md` and `../docs/REQUIREMENTS.md`.

The [standalone multi-agent workflow](app/agents/workflow/README.md) now connects
triage -> router -> RAG/data/both -> response in one LangGraph graph. ChromaDB
remains the policy vector database; the data agent uses read-only SQLite templates.

```powershell
uv run python -m app.agents.workflow "Check SKU1001 at ST001 and explain replenishment policy"
uv run pytest tests/test_workflow.py tests/test_rag.py tests/test_api.py
```

The API remains disconnected. Authentication, ticket writes, and chat persistence
are not implemented by this workflow.

The RAG module has its own setup and verification instructions. The database importer
and source-to-database verification previously ran successfully; the broader
application roadmap remains unimplemented.

The revised contract in `openapi.json` is a proposal, not the generated schema of current routes. Employee ID + Store ID/JWT login, employee-scoped Dashboard/Analytics, chatbot agents, persistent tickets, and the new automated suites remain unimplemented. Existing dashboard code is unscoped. See `../docs/API_CONTRACT.md`, `../docs/TICKET_DATA_MODEL.md`, and `../docs/AUTOMATED_TEST_DESIGN.md` for the planned behaviour.
