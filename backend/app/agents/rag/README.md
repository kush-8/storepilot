# Standalone policy RAG

This module uses LangChain for the RAG pipeline, LangGraph for orchestration,
Groq (`langchain-groq`) for generation, and **ChromaDB** for the local persistent
vector database through `langchain-chroma`.
Its module is independent of FastAPI. The API calls it through the shared LangGraph workflow
and Copilot service; the standalone CLI remains available.
It reads only the configured policy Markdown directory, never retail data,
conversations, tickets, or evaluation answers.

## Folder structure and responsibilities

```text
rag/
  config.py                    Environment and path configuration
  schemas.py                   Public evidence and answer contracts
  service.py                   RagAgent facade and dependency composition
  __main__.py                  Standalone CLI
  ingestion/
    loader.py                  LangChain BaseLoader -> Document objects
    splitter.py                Markdown headings + 1000-character chunks, overlap 150
  retrieval/
    embeddings.py              LangChain Embeddings adapter for local ONNX MiniLM
    vector_store.py            ChromaDB collection lifecycle, LangChain Chroma adapter
    index.py                   Explicit indexing, versioning, idempotency
    retriever.py               LangChain BaseRetriever, distance filtering
  generation/
    model.py                   ChatGroq and structured response configuration
    prompts.py                 ChatPromptTemplate and grounding instructions
    chain.py                   Runnable context formatter | prompt | model
    validation.py              Citation validation and abstention
  workflow/
    state.py                   Typed graph input, state, and output
    nodes.py                   Adapters calling retrieval, generation, validation
    graph.py                   LangGraph nodes and edges only
```

The loader and splitter exchange LangChain `Document` objects. Indexing uses
`Chroma.add_documents`; retrieval uses `Chroma.similarity_search_with_score`
inside a `BaseRetriever`, retaining raw cosine distance in document metadata.
The small ONNX adapter implements LangChain's `embed_documents` and `embed_query`
interfaces, preserving the existing CPU model/cache without a second embedding API.
Native Chroma calls are limited to collection readiness/version lifecycle metadata.

LangChain dependencies use their modular packages: `langchain-core`,
`langchain-text-splitters`, `langchain-chroma`, and `langchain-groq`.

## Run

From `backend/`:

```powershell
uv sync --locked
uv run python -m app.agents.rag index
uv run python -m app.agents.rag retrieve "When does a refund require manager approval?"
uv run python -m app.agents.rag ask "When does a refund require manager approval?"
```

On this workstation, if `uv` is not on PATH, use
`../.tools/uv-package/bin/uv.exe` in its place.

`index` downloads Chroma's checksum-verified ONNX `all-MiniLM-L6-v2` embedding
model on first use (internet needed), then embeds policies locally on CPU.
Weights and vectors live in ignored `backend/.cache/`. No embedding API key is
needed. `retrieve` is local after setup. `ask` sends the question and up to four
retrieved sections to Groq, using `GROQ_API_KEY` from the existing `backend/.env`.
Never put credentials or personal/payment data in CLI questions.

`GROQ_MODEL` defaults to `openai/gpt-oss-120b` (served by Groq, using only your Groq
key, using native strict JSON-schema outputs) and can be changed to a Groq
chat model supporting tool/function calling. Environment variables take precedence
over `.env`; see `backend/.env.example` for all settings. Relative paths are
resolved against `backend/`, regardless of the caller's working directory.

## Use from Python

```python
from app.agents.rag import PolicyIndex, RagSettings, create_rag_agent

settings = RagSettings.from_env()
PolicyIndex(settings).build()  # Explicit setup job, not per question.

agent = create_rag_agent(settings)
result = agent.ask("What should I do if all registers cannot take card payments?")
print(result.answer)
print(result.model_dump())

# The compiled LangGraph can also be used directly or composed in a future graph.
state = await agent.graph.ainvoke({"question": "What is the no-receipt return policy?"})
result = state["result"]
```

For retrieval as a composable LangChain runnable:

```python
retriever = PolicyIndex(settings).as_retriever()
documents = retriever.invoke("What is the no-receipt return policy?")
# Each Document contains the original section text and citation metadata.
```

For dependency injection, construct `RagAgent(retriever, answer_chain)` with a
LangChain retriever/runnable returning Documents and a runnable returning
`GeneratedAnswer`. `generation.chain.build_answer_chain(model)` composes the
context formatter, prompt template, and structured model. An alternate LangChain
embedding implementation can be passed to `PolicyIndex(settings, embeddings,
embedding_id="provider-model-version")`; changing its configuration requires a
different embedding ID and an explicit index build.

## Workflow and evidence

`START -> retrieve -> generate -> validate -> END`; empty retrieval takes an
`abstain` branch without calling Groq. Model timeout/retry limits are bounded.
Provider failures return `model_unavailable`; malformed responses or invented
citation IDs return `invalid_response`, without displaying unvalidated model text.
The CLI exits nonzero on these errors and on missing configuration/index setup.

Policies are split structurally at `##` headings with `MarkdownHeaderTextSplitter`,
then `RecursiveCharacterTextSplitter` divides each section into chunks of at most
**1,000 characters** with **150 characters of target overlap**. Paragraph, line,
and word boundaries are preferred; overlap can be smaller at structural boundaries
and never crosses sections. Source-line enrichment retains the original text
instead of its whitespace-normalized preview.
Single-chunk citations retain `Source ID:heading-slug`; split sections append
`:chunk-N` to give every chunk a unique citation ID. Citations also retain the
parent section ID, chunk index/count, exact character offsets within the trimmed
section body, and the parent section's source-line range, alongside
filename, title, heading, source line range, full source SHA-256, and section text.
Each answer statement must cite retrieved IDs. Final citation metadata comes from
the original policy files, not the model. Citation validation checks membership,
not semantic entailment: human review/evaluation is still needed for answer quality.

The index name incorporates source content, parser version, embedding configuration,
and distance metric. Re-running `index` is idempotent. Edits/removals create a new
version, preventing stale sections from entering subsequent queries; older collections
remain on disk. Queries refuse missing/incomplete/stale indexes and never rebuild
them. Do not edit policies while an index build is running.

Results include `status`, `answer`, `citations`, and `retrieved_sections`. Cosine
distance is a retrieval measure, **not** answer/classification confidence.
`RAG_MAX_DISTANCE=0.65` is an initial threshold, not an evaluated guarantee; tune
against representative questions before the demo. The generator also abstains when
retrieved content cannot answer the question. Missing indexes raise
`IndexNotReadyError`; build them explicitly before using the agent.

## Scope

This is a stateless specialist RAG graph. Its Python interface expects an already
sanitized question. PII/safety/router agents, multi-turn memory, deterministic
priority/approval enforcement, SQL access, ticket creation, and HTTP integration
are separate future work. Prompt instructions and citation validation do not
replace those boundaries. No checkpointer or conversation persistence is enabled.

## Verification

```powershell
uv run pytest tests/test_rag.py
uv run ruff check app/agents tests/test_rag.py
```

Tests use deterministic embeddings with real temporary Chroma collections and
injected model responses; they require neither network downloads nor a Groq key.
For a real model smoke test, run the `index` and `ask` commands above.

Implementation references: [LangGraph graph API](https://docs.langchain.com/oss/python/langgraph/graph-api),
[ChatGroq](https://docs.langchain.com/oss/python/integrations/chat/groq),
[LangChain Chroma integration](https://docs.langchain.com/oss/python/integrations/vectorstores/chroma),
[Markdown splitting](https://docs.langchain.com/oss/python/integrations/splitters/markdown_header_metadata_splitter),
[Chroma embeddings](https://docs.trychroma.com/docs/embeddings/embedding-functions).
