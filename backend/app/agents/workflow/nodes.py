import logging

from langchain_core.runnables import RunnableConfig

from ..data.agent import DataAgent
from ..rag.schemas import RagResult
from ..rag.service import RagAgent
from ..router.agent import RouterAgent
from ..triage.agent import TriageAgent
from .input import prepare_question
from .response import compose_result
from .schemas import WorkflowState

logger = logging.getLogger(__name__)


class WorkflowNodes:
    def __init__(self, triage: TriageAgent, router: RouterAgent, rag: RagAgent, data: DataAgent):
        self.triage, self.router, self.rag, self.data = triage, router, rag, data

    def triage_agent(self, state: WorkflowState, config: RunnableConfig):
        question = prepare_question(state["question"])
        try:
            return {"question": question, "triage_result": self.triage.invoke(question, config)}
        except Exception as exc:
            logger.warning("Triage failed (%s)", type(exc).__name__)
            return {
                "question": question,
                "error": "Triage is unavailable. Please retry or seek review.",
            }

    def router_agent(self, state: WorkflowState, config: RunnableConfig):
        try:
            return {"route_decision": self.router.invoke(state["triage_result"], config)}
        except Exception as exc:
            logger.warning("Router failed (%s)", type(exc).__name__)
            return {"error": "Routing is unavailable. Please retry or seek review."}

    def rag_agent(self, state: WorkflowState, config: RunnableConfig):
        try:
            question = state["route_decision"].policy_question or (
                "Explain only the policy rules and procedures relevant to this request. "
                "Database facts will be handled by a separate agent. Request: "
                + state["triage_result"].summary
            )
            result = self.rag.graph.invoke({"question": question}, config=config)["result"]
        except Exception as exc:
            logger.warning("RAG specialist failed (%s)", type(exc).__name__)
            result = RagResult(
                status="model_unavailable",
                answer="Policy retrieval is unavailable. "
                "Run the RAG index setup or seek human review.",
            )
        return {"rag_result": result}

    def data_agent(self, state: WorkflowState, config: RunnableConfig):
        return {
            "data_result": self.data.invoke(
                state["question"],
                state["route_decision"],
                state["triage_result"],
                state.get("viewer_employee_id"),
                config,
            )
        }

    def compose(self, state: WorkflowState):
        return {"result": compose_result(state)}
