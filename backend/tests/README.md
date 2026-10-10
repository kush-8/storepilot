# StorePilot backend tests

The current suite has **282 passing cases**. See the
[workflow, endpoint and verification report](../../docs/COPILOT_WORKFLOW_AND_TESTS.md)
for all 16 API explanations, suite coverage and remaining work.

## Run

From `backend/`:

```powershell
uv sync --locked
uv run pytest -q
uv run ruff check app scripts tests
```

Test dependencies are declared in the `dev` group of `pyproject.toml` and locked in `uv.lock`.
There is no separate test requirements file. On this workstation use
`..\.tools\bin\uv.exe` if uv is absent from PATH. Windows TestClient may need execution
outside the sandbox to create its local asyncio loopback sockets.

## Test boundaries

`agent_fakes.py` supplies deterministic structured model replies and policy retrieval to the
actual compiled workflow. The graph, RAG validation, read-only SQL tool, JWT verification,
HTTP handlers and SQLite transactions remain real. External network calls are disabled.
RAG tests also exercise real temporary Chroma storage.

`conftest.py` copies the source database, adds four synthetic directory employees and initializes
temporary application storage through the runtime. `support.py` independently signs valid and
adversarial JWTs and checks responses against the maintained OpenAPI contract. API integration
fixtures create tickets through public endpoints. Visibility tests cover every viewer/creator
level combination, dashboard totals, analytics and pagination; additional checks cover rollback,
expiry, status events and exact date boundaries.

Source tests open `database/retail.db` read-only and verify integrity, relationships, counts and
seeded observations. Removed operational CSVs are neither required nor reconstructed.

## Cleanup and remaining work

Six obsolete test modules (97 cases) required a superseded orchestrator, normalized fixture tables
or an evaluation runner that does not exist. They were removed, along with their unused collaborators,
SQL fixture and duplicate test catalogues. The useful unique auth/policy tests were migrated,
and missing persistence/visibility regressions were retained against actual interfaces.
No skipped or expected-failure cases disguise incomplete runtime features.

Live model quality, backend evaluation, Docker persistence and frontend browser journeys still
need their own implementation and verification. The evaluation input files and
[broader test design](../../docs/AUTOMATED_TEST_DESIGN.md) are retained.
