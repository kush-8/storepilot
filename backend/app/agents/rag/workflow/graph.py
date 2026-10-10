"""Graph topology only; RAG behavior lives in dedicated modules."""

from langchain_core.runnables import Runnable
from langgraph.graph import END, START, StateGraph

from .nodes import RagNodes
from .state import RagInput, RagOutput, RagState


def build_rag_graph(retriever: Runnable, answer_chain: Runnable):
    nodes = RagNodes(retriever, answer_chain)
    graph = StateGraph(RagState, input_schema=RagInput, output_schema=RagOutput)
    graph.add_node("retrieve", nodes.retrieve)
    graph.add_node("generate", nodes.generate)
    graph.add_node("validate", nodes.validate)
    graph.add_node("abstain", nodes.abstain)
    graph.add_edge(START, "retrieve")
    graph.add_conditional_edges(
        "retrieve",
        lambda state: "generate" if state["sections"] else "abstain",
        {"generate": "generate", "abstain": "abstain"},
    )
    graph.add_edge("generate", "validate")
    graph.add_edge("validate", END)
    graph.add_edge("abstain", END)
    return graph.compile()
