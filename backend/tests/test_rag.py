"""Offline behavior tests for the standalone RAG graph and real Chroma persistence."""

import io
import json
import math
import sys
from unittest.mock import Mock

import pytest
from langchain_core.documents import Document
from langchain_core.embeddings import Embeddings
from langchain_core.runnables import RunnableLambda
from pydantic import ValidationError

from app.agents.rag import IndexNotReadyError, PolicyIndex, RagAgent, RagSettings, create_rag_agent
from app.agents.rag.config import BACKEND_ROOT
from app.agents.rag.generation.chain import build_answer_chain
from app.agents.rag.ingestion import load_policy_documents
from app.agents.rag.ingestion.splitter import PolicySectionSplitter
from app.agents.rag.schemas import (
    GeneratedAnswer,
    GroundedStatement,
    PolicySection,
    RagResult,
    RetrievedSection,
)


def load_policy_sections(directory):
    return [PolicySection.from_document(doc) for doc in load_policy_documents(directory)]


def make_agent(retriever, model):
    def retrieve(question):
        return [
            Document(page_content=section.text, metadata=section.model_dump(exclude={"text"}))
            for section in retriever.search(question)
        ]

    chain = build_answer_chain(RunnableLambda(lambda prompt: model.invoke(prompt.to_messages())))
    return RagAgent(RunnableLambda(retrieve), chain)


class TestEmbeddings(Embeddings):
    __test__ = False
    fingerprint = "test-three-dimensional-v1"

    def embed_documents(self, texts):
        vectors = []
        for text in texts:
            values = [text.lower().count("refund"), text.lower().count("payment"), 0.01]
            norm = math.sqrt(sum(value * value for value in values))
            vectors.append([value / norm for value in values])
        return vectors

    def embed_query(self, text):
        return self.embed_documents([text])[0]


@pytest.fixture
def settings(tmp_path):
    policies = tmp_path / "policies"
    policies.mkdir()
    (policies / "policy.md").write_text(
        "# Retail Policy\n\nSource ID: TEST-01\n\n"
        "## Refunds\n\nA refund of INR 5000 or more requires manager approval.\n\n"
        "## Payments\n\nPayment failures require payment support review.\n",
        encoding="utf-8",
    )
    return RagSettings(knowledge_base_path=policies, chroma_path=tmp_path / "chroma")


@pytest.fixture
def section(settings):
    first = load_policy_sections(settings.knowledge_base_path)[0]
    return RetrievedSection(**first.model_dump(), distance=0.1)


def test_supplied_policy_sections_have_resolvable_lines_and_stable_ids():
    sections = load_policy_sections(BACKEND_ROOT / "knowledge_base")
    assert len({item.filename for item in sections}) == 5
    assert len({item.section_id for item in sections}) == len(sections)
    for section in sections:
        lines = (BACKEND_ROOT / "knowledge_base" / section.filename).read_text().splitlines()
        assert lines[section.line_start - 1] == f"## {section.heading}"
        body = "\n".join(lines[section.line_start : section.line_end]).strip()
        assert section.text == body[section.chunk_start : section.chunk_end]
        assert len(section.text) <= 1000
        assert len(section.source_hash) == 64


def test_structure_splitter_bounds_chunks_overlaps_and_preserves_citations():
    body = "abcdefghij" * 700
    document = Document(
        page_content=f"# Policy\nSource ID: TEST-01\n\n## Long section\n\n{body}\n\n"
        "## Another section\n\nSeparate rules.",
        metadata={"filename": "policy.md", "source_hash": "source-hash"},
    )
    splitter = PolicySectionSplitter()
    chunks = splitter.transform_documents([document])
    long_chunks = [chunk for chunk in chunks if chunk.metadata["heading"] == "Long section"]
    assert len(long_chunks) > 1
    assert len({chunk.id for chunk in chunks}) == len(chunks)
    for index, chunk in enumerate(long_chunks):
        metadata = chunk.metadata
        assert 0 < len(chunk.page_content) <= 1000
        assert metadata["parent_section_id"] == "TEST-01:long-section"
        assert metadata["chunk_index"] == index
        assert metadata["chunk_count"] == len(long_chunks)
        assert chunk.page_content == body[metadata["chunk_start"] : metadata["chunk_end"]]
        assert metadata["source_hash"] == "source-hash"
        if index:
            previous = long_chunks[index - 1]
            assert previous.metadata["chunk_end"] - metadata["chunk_start"] == 150
            assert previous.page_content[-150:] == chunk.page_content[:150]
    assert long_chunks[-1].metadata["chunk_end"] == len(body)
    assert chunks[-1].page_content == "Separate rules."
    assert chunks[-1].id == "TEST-01:another-section"
    assert chunks == splitter.transform_documents([document])


def test_real_chroma_index_is_idempotent_and_reopens(settings):
    embeddings = TestEmbeddings()
    index = PolicyIndex(settings, embeddings)
    report = index.build()
    assert report["sections"] == 2
    assert report["status"] == "indexed"
    embeddings.embed_documents = Mock(
        side_effect=AssertionError("must not re-embed unchanged policies")
    )
    assert index.build()["status"] == "unchanged"
    reopened = PolicyIndex(settings, TestEmbeddings())
    results = reopened.search("refund")
    assert [item.section_id for item in results] == ["TEST-01:refunds"]
    assert results[0].line_start == 5


def test_missing_and_changed_index_fail_until_explicit_rebuild(settings):
    index = PolicyIndex(settings, TestEmbeddings())
    with pytest.raises(IndexNotReadyError):
        index.search("refund")
    assert not settings.chroma_path.exists()
    original = index.build()
    path = settings.knowledge_base_path / "policy.md"
    path.write_text("# Policy\nSource ID: TEST-01\n## New\nNew refund policy.", encoding="utf-8")
    with pytest.raises(IndexNotReadyError):
        index.search("refund")
    changed = index.build()
    assert original["collection"] != changed["collection"]
    assert [item.section_id for item in index.search("refund")] == ["TEST-01:new"]


def test_embedding_configuration_change_requires_reindex(settings):
    PolicyIndex(settings, TestEmbeddings()).build()
    changed = TestEmbeddings()
    changed.fingerprint = "test-three-dimensional-v2"
    with pytest.raises(IndexNotReadyError):
        PolicyIndex(settings, changed).search("refund")


def test_langchain_retriever_and_chain_work_together(settings):
    index = PolicyIndex(settings, TestEmbeddings())
    index.build()

    def answer(prompt):
        messages = prompt.to_messages()
        assert "manager approval" in messages[-1].content
        return GeneratedAnswer(
            insufficient_evidence=False,
            statements=[
                GroundedStatement(
                    text="Refunds of INR 5000 or more require approval.",
                    citation_ids=["TEST-01:refunds"],
                ),
            ],
        )

    retriever = index.as_retriever()
    agent = RagAgent(retriever, build_answer_chain(RunnableLambda(answer)))
    result = agent.ask("refund")
    assert result.status == "answered"
    assert result.citations[0].filename == "policy.md"
    assert len(result.retrieved_sections) == 1

    # A long-lived agent must detect source edits, not retain a stale collection.
    with (settings.knowledge_base_path / "policy.md").open("a") as file:
        file.write("\n## Review\nRefund review policy changed.\n")
    with pytest.raises(IndexNotReadyError):
        agent.ask("refund")


def test_duplicate_policy_sections_rejected(settings):
    path = settings.knowledge_base_path / "policy.md"
    with path.open("a") as file:
        file.write("\n## Refunds\nDuplicate section.")
    with pytest.raises(ValueError, match="duplicate"):
        load_policy_sections(settings.knowledge_base_path)


def test_answer_contains_only_citations_from_retrieved_evidence(section):
    model = Mock()
    model.invoke.return_value = GeneratedAnswer(
        insufficient_evidence=False,
        statements=[
            GroundedStatement(
                text="Manager approval is required.", citation_ids=[section.section_id]
            ),
        ],
    )
    retriever = Mock()
    retriever.search.return_value = [section]
    result = make_agent(retriever, model).ask("Does this refund require approval?")
    assert result.status == "answered"
    assert f"[{section.section_id}]" in result.answer
    assert result.citations == [section]
    assert section.text in model.invoke.call_args.args[0][1].content


def test_empty_retrieval_does_not_call_groq():
    retriever, model = Mock(), Mock()
    retriever.search.return_value = []
    result = make_agent(retriever, model).ask("What is the moon made of?")
    assert result.status == "insufficient_evidence"
    assert not result.citations
    model.invoke.assert_not_called()


@pytest.mark.parametrize(
    "draft",
    [
        {
            "insufficient_evidence": False,
            "statements": [
                {"text": "Invented policy", "citation_ids": ["FAKE:policy"]},
            ],
        },
        {
            "insufficient_evidence": False,
            "statements": [
                {"text": "Uncited answer", "citation_ids": []},
            ],
        },
        {"unexpected": "malformed output"},
    ],
)
def test_invalid_model_output_is_not_exposed(section, draft):
    retriever, model = Mock(), Mock()
    retriever.search.return_value = [section]
    model.invoke.return_value = draft
    result = make_agent(retriever, model).ask("refund")
    assert result.status == "invalid_response"
    assert not result.citations
    assert "Invented policy" not in result.answer
    assert "Uncited answer" not in result.answer


def test_model_can_abstain_despite_vector_match(section):
    retriever, model = Mock(), Mock()
    retriever.search.return_value = [section]
    model.invoke.return_value = GeneratedAnswer(insufficient_evidence=True, statements=[])
    assert make_agent(retriever, model).ask("unrelated question").status == "insufficient_evidence"


def test_provider_error_does_not_expose_request_or_key(section):
    retriever, model = Mock(), Mock()
    retriever.search.return_value = [section]
    model.invoke.side_effect = TimeoutError("secret-api-key and raw provider payload")
    result = make_agent(retriever, model).ask("refund")
    assert result.status == "model_unavailable"
    assert "secret-api-key" not in result.model_dump_json()


@pytest.mark.parametrize("question", ["", "   ", "x" * 4001])
def test_invalid_input_does_not_retrieve_or_generate(question):
    retriever, model = Mock(), Mock()
    with pytest.raises(ValueError, match="Question"):
        make_agent(retriever, model).ask(question)
    retriever.search.assert_not_called()
    model.invoke.assert_not_called()


def test_repeated_calls_do_not_reuse_old_answer_or_evidence(section):
    retriever, model = Mock(), Mock()
    retriever.search.side_effect = [[section], []]
    model.invoke.return_value = GeneratedAnswer(
        insufficient_evidence=False,
        statements=[
            GroundedStatement(text="Approval required", citation_ids=[section.section_id]),
        ],
    )
    agent = make_agent(retriever, model)
    assert agent.ask("refund").status == "answered"
    second = agent.ask("another question")
    assert second.status == "insufficient_evidence"
    assert not second.retrieved_sections
    assert model.invoke.call_count == 1


def test_env_configuration_uses_backend_paths_without_revealing_key(monkeypatch):
    monkeypatch.setenv("GROQ_API_KEY", "private-test-key")
    monkeypatch.setenv("RAG_CHROMA_PATH", "custom-index")
    settings = RagSettings.from_env()
    assert settings.chroma_path == BACKEND_ROOT / "custom-index"
    assert "private-test-key" not in repr(settings)
    assert "private-test-key" not in settings.model_dump_json()


def test_missing_key_is_actionable_and_config_bounds_are_enforced():
    with pytest.raises(ValueError, match="GROQ_API_KEY"):
        create_rag_agent(RagSettings())
    with pytest.raises(ValidationError):
        RagSettings(top_k=5)


def test_rag_import_does_not_import_fastapi_app():
    # Other suites may already import main; only run this assertion in isolation.
    import subprocess

    process = subprocess.run(
        [
            sys.executable,
            "-c",
            "import sys; import app.agents.rag; assert 'app.main' not in sys.modules",
        ],
        capture_output=True,
        text=True,
        check=False,
    )
    assert process.returncode == 0, process.stderr


def test_cli_json_handles_unicode_in_legacy_windows_console(monkeypatch):
    from app.agents.rag import __main__ as cli

    agent = Mock()
    agent.ask.return_value = RagResult(status="answered", answer="Refund \u20b95,000 \u2014 review")
    monkeypatch.setattr(cli, "create_rag_agent", lambda settings: agent)
    monkeypatch.setattr(cli.RagSettings, "from_env", lambda: RagSettings())
    monkeypatch.setattr(sys, "argv", ["rag", "ask", "refund"])
    buffer = io.BytesIO()
    console = io.TextIOWrapper(buffer, encoding="ascii")
    monkeypatch.setattr(sys, "stdout", console)
    assert cli.main() == 0
    console.flush()
    assert json.loads(buffer.getvalue())["answer"] == "Refund \u20b95,000 \u2014 review"
