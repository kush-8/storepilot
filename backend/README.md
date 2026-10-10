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

Agent orchestration and additional API endpoints are planned in `../docs/SYSTEM_DESIGN.md` and `../docs/REQUIREMENTS.md`.

Further implementation is paused for document review. The database importer and source-to-database verification have run successfully; backend test/lint checks have not been completed.

The revised contract in `openapi.json` is a proposal, not the generated schema of current routes. Employee ID + Store ID/JWT login, employee-scoped Dashboard/Analytics, chatbot agents, persistent tickets, and the new automated suites remain unimplemented. Existing dashboard code is unscoped. See `../docs/API_CONTRACT.md`, `../docs/TICKET_DATA_MODEL.md`, and `../docs/AUTOMATED_TEST_DESIGN.md` for the planned behaviour.
