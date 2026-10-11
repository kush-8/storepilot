# StorePilot agent workflow

The workflow is connected to FastAPI through `app/services/copilot.py` and
`app/dependencies.py`. Agents remain usable without importing the HTTP application.

```mermaid
flowchart TD
    Q[Issue or follow-up] --> P[PII agent]
    P --> S[Safety agent]
    S -->|Allowed| T[Triage agent]
    S -->|Refused| C[Safe response]
    T --> R[Router agent]
    R -->|RAG| G[Policy RAG: Chroma + Groq]
    R -->|Data| D[Data agent: validated read-only SQL]
    R -->|Both| G
    R -->|Both| D
    R -->|Clarify or refuse| C
    G --> C
    D --> C
    C --> V[Application validation and draft]
    V --> U[Employee explicitly saves ticket]
    U --> DB[Application SQLite database]
    A[Dashboard analytics question] --> P2[PII and Safety]
    P2 --> D2[Same DataAgent: LLM-generated analytics SELECT]
    D2 --> T2[Validated read-only analytics SQL tool]
    T2 --> E2[Final LLM explanation: at most 20 words]
    E2 --> UI[Supporting results first, explanation last]
    DB --> F[Current employee scope and date filters]
    F --> D2
```

## Separation of concerns

- `guardrails/`: local normalization, PII redaction and safety decisions; no HTTP/database/model calls.
- `triage/`: structured interpretation, explicit-ID grounding and provisional confidence/priority.
- `router/`: selects RAG, Data, Both, clarification or refusal. Policy advice cannot use Data alone.
- `rag/`: Markdown ingestion, bounded chunks, local embeddings, Chroma retrieval, Groq generation,
  citation checks and output safety validation.
- `data/agent.py`: operational SQL planning and dashboard analytics on the same agent instance.
- `data/sql_tool.py`: SQL AST checks, table/column/function restrictions, read-only SQLite,
  row/execution caps, mandatory historical windows, current-level authorization for cases.
- `data/analytics.py`: structured analytics SQL plans, explicit bindings and result contracts.
- `data/analytics_sql_tool.py`: validated SQL against isolated, pre-scoped public data; read-only
  execution with row and work limits. Ticket text, identities and rows never reach the planner.
- `data/analytics_answer.py`: final explanation of verified public results, capped at 20 words;
  row-reference, numeric-claim and output guardrail checks with a brief fallback.
- `workflow/graph.py`: guardrails, conditional dispatch, parallel specialists and one join.
- `workflow/response.py`: safe result composition; partial evidence requires human review.
- `app/services/copilot.py`: public ChatTurn adaptation, citation hashes, priority/refund rules,
  escalation and server-held draft construction.
- `app/main.py`: authentication, request validation, private persistence, retries and ticket commits.

The API injects verified caller identity. Validated selected store/SKU context takes precedence
over model extraction. The standalone CLI employee argument is a trusted local caller argument,
not authentication. No graph checkpointer is configured; do not enable external tracing of raw inputs.

## Setup and use

From `backend`:

```powershell
uv sync --locked
# Configure GROQ_API_KEY and JWT_SECRET in .env; use .env.example as the template.
uv run python -m app.agents.rag index
uv run python -m app.agents.workflow "Check SKU1001 stock at ST001 and advise replenishment"
uv run uvicorn app.main:app --reload --host 127.0.0.1 --port 8000
```

Index creation is an explicit setup action. It downloads local ONNX embeddings once and indexes
28 current chunks; policy edits require rebuilding. Retrieval and indexing need no Groq key.
Triage, routing, policy answer generation, SQL planning and analytics planning require Groq.
A missing key/provider/index produces unavailable/partial results, never a fabricated success.

`RetailWorkflow.ask(question, viewer_employee_id=..., entity_context=...)` returns a typed
`WorkflowResult`. Every graph invocation starts with PII then Safety; a refusal runs no models
or tools. The triage stage precedes routing because the existing router consumes structured triage.
Triage uses ten hand-written question/JSON demonstrations in `triage/prompts.py`, covering all
eight categories, intent types, priority levels, explicit IDs, historical filters, clarification
and restricted requests. They are fixed examples, not retrieved historical case labels. Example
outputs are validated with `TriageResult`, and the current question remains the final human message.
Both specialists run in one parallel superstep and compose once. Input/model/retrieved/output
text is sanitized at its boundaries. Regex safeguards remain bounded prototype detection.

Operational data is the immutable retail snapshot. Timestamp windows are `(start,end]` in IST,
anchored to 10 October 2026 noon; receipts have calendar-date precision. Case queries are scoped
before aggregation using creator current level <= viewer current level. The database tool imposes
these boundaries even when generated SQL omits them. Missing inventory is unknown, not zero.

Dashboard analytics uses the same DataAgent's `analyze` method with tickets already scoped by
`app/reporting.py`. Live mode reads persisted Copilot tickets; historical mode reads imported
support cases; combined mode includes both. The LLM generates SQL for rankings, trends,
comparisons and operational data questions. A separate tool executes it, then a final LLM explains
the verified results in at most 20 words. The frontend places supporting results before that
explanation. Policies use the existing RAG agent. Structured filters and
private clarification threads are retained. See [analytics workflow](../../../../docs/ANALYTICS_WORKFLOW.md).

The graph returns guidance. Explicit `POST /api/tickets` commits an eligible draft. It does not
approve refunds, notify people, execute transfers or change inventory. Partial/invalid/low-confidence
answers cannot produce a validated saveable draft. Urgent incidents still receive escalation guidance.

See [workflow and verification report](../../../../docs/COPILOT_WORKFLOW_AND_TESTS.md) for API
sequence, every endpoint, test commands, results and remaining legacy-suite limitations.
