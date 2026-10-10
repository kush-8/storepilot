"""Public application facade and dependency composition; no HTTP dependencies."""

from langchain_core.runnables import Runnable

from .config import RagSettings
from .generation.chain import build_answer_chain
from .generation.model import create_answer_model
from .retrieval import PolicyIndex
from .schemas import RagResult
from .workflow.graph import build_rag_graph


class RagAgent:
    def __init__(self, retriever: Runnable, answer_chain: Runnable):
        self.graph = build_rag_graph(retriever, answer_chain)

    def ask(self, question: str) -> RagResult:
        return self.graph.invoke({"question": question})["result"]


def create_rag_agent(settings: RagSettings | None = None) -> RagAgent:
    settings = settings or RagSettings.from_env()
    model = create_answer_model(settings)
    return RagAgent(PolicyIndex(settings).as_retriever(), build_answer_chain(model))
