"""One compiled graph; both specialists run in the same parallel superstep."""

from langgraph.graph import END, START, StateGraph

from .nodes import WorkflowNodes
from .schemas import WorkflowInput, WorkflowOutput, WorkflowState


def dispatch(state: WorkflowState) -> list[str]:
    if state.get("error"):
        return ["compose"]
    return {
        "rag": ["rag_agent"],
        "data": ["data_agent"],
        "both": ["rag_agent", "data_agent"],
        "clarify": ["compose"],
        "refuse": ["compose"],
    }[state["route_decision"].route]


def build_workflow(nodes: WorkflowNodes):
    graph = StateGraph(WorkflowState, input_schema=WorkflowInput, output_schema=WorkflowOutput)
    for name in ("triage_agent", "router_agent", "rag_agent", "data_agent", "compose"):
        graph.add_node(name, getattr(nodes, name))
    graph.add_edge(START, "triage_agent")
    graph.add_conditional_edges(
        "triage_agent",
        lambda state: "compose" if state.get("error") else "router_agent",
        {"compose": "compose", "router_agent": "router_agent"},
    )
    graph.add_conditional_edges("router_agent", dispatch, ["rag_agent", "data_agent", "compose"])
    # Both branches write separate state channels and finish in one superstep;
    # LangGraph schedules this shared successor once with both results present.
    graph.add_edge("rag_agent", "compose")
    graph.add_edge("data_agent", "compose")
    graph.add_edge("compose", END)
    return graph.compile()
