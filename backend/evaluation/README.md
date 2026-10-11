# Backend workflow evaluation

Run all 11 cases in `public_test_cases.csv` through the production `RetailWorkflow.ask` graph:

```powershell
cd backend
.\.venv\Scripts\python.exe -m evaluation
```

Use `uv run python -m evaluation` with uv. Configure Groq in the existing backend `.env`
and build the policy index with `python -m app.agents.rag index` first. The runner uses
the configured provider, actual Chroma retrieval and SQL validation. It sends sanitized
prompts and permitted policy context to Groq. It creates an isolated copy of the source
database, reads it through the existing read-only executor, and never imports application
storage or saves tickets. Employee identity is resolved from each case's supplied persona
and the actual employee directory; current numeric level visibility stays enforced. If
that persona has no employee in a mentioned store, the first employee of that role is used.
The manifest and results record the resulting scope. This tests the standalone graph,
not the HTTP Copilot adapter's additional priority/draft validation.

Outputs are written to a new ignored `evaluation/outputs/<UTC timestamp>/` directory:

- `predictions.csv`: exact 12-column submission order, Yes/No booleans and semicolon lists.
- `results.jsonl`: actual typed results, timings, scoped caller, observed tables and per-case checks.
- `report.json` and `report.md`: metrics with exact denominators, targets and failures.
- `manifest.json`: model/embedding settings, fixed historical anchor, input/policy/source hashes.
- `retail.snapshot.db`: isolated source used for this run.

Expected labels, sources and behavior never enter inference. Escalation is derived guidance
from the observed priority/review requirement and source escalation matrix; no notification
is sent. `data_used` retains legacy CSV provenance names from `import_manifest`, although
execution uses SQLite. `pii_masked=Yes` means detected input PII was absent from the answer;
the safety score also checks the full typed result for leaks.

Default pacing waits 45 seconds between cases. Use `--case-delay 0` only with sufficient
provider capacity, or `--case-delay 60` for slower pacing. `--output-dir <new directory>`
selects an output folder; existing folders are never overwritten. Each run is retained,
including connection failures and rate limits. There are no evaluator retries that choose
the best prediction. Exit codes: 0 = measured targets met, 1 = quality targets missed,
2 = setup/provider unavailability or source integrity failure. Semantic behavior can still
fail when automated targets pass.

Category and priority accuracy include all 11 cases. Citation presence, expected-source
hit and retrieval hit also include all 11, including local refusals that intentionally skip
RAG. Citation validity only considers cases with citations. Data-use coverage considers
five cases and checks actual executed tables; it cannot establish correct SQL filters,
joins, totals or causal interpretation. Safety measures the two explicit security/PII cases.
Human approval, neutral language, correct root cause, and citation entailment require
separate inspection of the recorded results. Unavailable cases count as failures rather
than being omitted from quality metrics.

Verify the evaluator without external model calls:

```powershell
.\.venv\Scripts\python.exe -m pytest tests/test_evaluation.py -q
.\.venv\Scripts\python.exe -m ruff check evaluation tests/test_evaluation.py
```
