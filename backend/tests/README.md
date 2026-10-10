# StorePilot TDD tests

Only test code, fixtures, isolated test dependencies and test documentation were generated. Application code, runtime schema, OpenAPI, application manifests and uv.lock are unchanged. Missing routes/production workflow interfaces fail explicitly: there are no xfail or skip markers masking unimplemented features.

Read [API_FLOW_AND_TESTS.md](API_FLOW_AND_TESTS.md) for the app/request flow and all 16 endpoint explanations. [TEST_CATALOG.md](TEST_CATALOG.md) lists individual backend cases and recorded results. [Browser tests](../../frontend/tests/README.md) cover the React flows.

## Run the tests

From `backend/` in PowerShell:

```powershell
..\.tools\bin\uv.exe sync --locked --group dev
..\.tools\bin\uv.exe pip install --python .venv\Scripts\python.exe -r tests\requirements.txt
.\.venv\Scripts\python.exe -m pytest -q
.\.venv\Scripts\python.exe -m ruff check tests
```

Use the direct venv Python command after installing the additional test validators. A subsequent `uv sync` can remove packages absent from the app manifest; reinstall the test requirements if necessary. The requirements file is confined to the tests because changing application dependency declarations was outside this phase.

For one TDD slice:

```powershell
.\.venv\Scripts\python.exe -m pytest tests/test_auth.py -q
.\.venv\Scripts\python.exe -m pytest tests/test_visibility.py -q
.\.venv\Scripts\python.exe -m pytest tests/test_pipeline.py -q
```

On this Windows Codex host the full run required approval to run outside the sandbox because Starlette/asyncio uses a loopback socket pair. Sandbox permission failures are not application behaviour. Local loopback is allowed by the test network guard; external sockets and live model calls are disabled. Reports/caches are ignored under tests/.cache and test-results.

## What each suite proves

| Suite | Assertions and purpose |
| --- | --- |
| test_contract.py | Full OpenAPI 3.1 validation, 35 schemas, examples, unique operations, security, forbidden client authority and implemented route coverage |
| test_api.py | Public readiness, missing source DB handling, protected dashboard regression and preservation of retained source inputs |
| test_auth.py | Exact directory pair, independently verified JWT, invalid input/token/session cases, current directory authority and logout revocation |
| test_context_and_policies.py | Employee context, store/warehouse options and catalog text/hash resolution across all five policies |
| test_visibility.py | All 16 level combinations, list/count/chart/search/detail scope, current directory changes, private conversations and related evidence |
| test_chat_and_creation.py | Sanitized persisted turns, owner draft, server authority, atomic ticket save, idempotent/concurrent retries, rollback and immutable retail DB |
| test_ticket_lifecycle.py | Five transitions, creator-only writes, expected-version conflicts and event history |
| test_analytics.py | Authorized full aggregates/model context, private follow-ups, live/historical filter validation, window boundaries and injection-safe searches |
| test_pipeline.py | PII and Safety before ordinary tools, follow-ups, RAG/Data/Both, grounding, deterministic P1/approval/review rules and safe failures |
| test_evaluation.py | Backend-only evaluation has no label leakage/application writes, exact prediction columns and honest metrics/failures |
| test_database.py | SQLite snapshot integrity, foreign keys, all nine table counts, retained import provenance and seeded stock-out evidence |

The test catalogue expands parameterized cases, so test counts are larger than the number of Python test functions.

## Fixtures and future seams

Each HTTP test gets a copied retail.db and an independent temporary storepilot.db. The four synthetic employees E9001–E9004 have levels 1–4 and stores ST001–ST004. Each has one Open P2 and one Closed P3 ticket, with distinctive hidden-content sentinels. Counts are independently enumerated: total 2/4/6/8; unresolved 1/2/3/4. Signing keys and bearer tokens are test-only values.

`fixtures/application.sql` is a **test fixture**, not a deployed migration or database implementation. It gives real SQLite assertions a reviewable logical storage boundary. No runtime storepilot.db is created. `support.py` constructs adversarial tokens and validates responses against the existing OpenAPI; it does not implement the app's token verifier or authorization rules.

The source of truth is backend/database/retail.db. Operational CSVs were intentionally removed after import; tests neither require nor reconstruct them. Source checks open the snapshot read-only, verify its integrity, relationships and 2,970 records, and check the seeded inventory evidence. HTTP tests copy this SQLite database into temporary fixtures. The retained import_manifest is provenance, not a requirement to keep the original files. Evaluation CSVs and policy documents remain in backend/evaluation and backend/knowledge_base.

The future app may expose `app.main.create_app()`; otherwise HTTP tests use `app.main.app`. Configure source/application DB and JWT settings through environment values in `conftest.py`. Future `app.dependencies.get_model_adapter` and `get_policy_retriever` allow deterministic collaborator injection. Actual authentication, scope, queries and persistence remain production responsibilities.

Pipeline tests expect `app.services.orchestrator.build_workflow(model, retriever, data, clock)` to return an object with `invoke(state)`. State includes request/conversation IDs, employee/store IDs, message, history and entrypoint. Collaborator protocols: model `generate(stage, payload)` for route/compose; retriever `search(query, limit=4)`; data `execute(template_id, parameters, viewer_employee_id)`. These are test-defined adapter boundaries for later implementation, not an assertion that those modules exist today.

Evaluator tests expect `app.evaluation.runner.run_evaluation(cases, workflow, output_dir, retail_database, application_database)`. It calls the supplied workflow without expected labels, writes predictions.csv, and returns metrics with correct/total/rate plus failures. Its supplied workflow intentionally misclassifies one case to catch copied labels or fabricated success. This is not a real-model accuracy measurement.

## TDD order and limits

Implement one failing slice at a time: auth/current context → access scope → conversation and guardrails → draft/save transaction → lifecycle → dashboard/Analytics → evaluator → browser flows. Reach green for that slice, refactor, then rerun relevant regressions. Application implementation has not started in this phase.

These tests do not yet exercise an actual Chroma index, embedding relevance, paid/live model quality, all public evaluation prompts, rate-limit thresholds, 200-row truncation, historical seeding/deduplication, Docker startup/persistence, every validation/error branch, or the remaining accessibility/security browser cases in the earlier test design. Those require their own executable suites and fixture/contracts as those boundaries are introduced. The current suite is not complete release certification.

Recorded baseline and per-case outcomes are in [TEST_CATALOG.md](TEST_CATALOG.md). Passing schema/database tests do not mean the planned application is implemented; browser tests cannot prove backend authorization because their HTTP responses are mocked.
