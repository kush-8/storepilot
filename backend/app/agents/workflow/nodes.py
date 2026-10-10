import logging
import re

from langchain_core.runnables import RunnableConfig

from ..data.agent import DataAgent
from ..data.schemas import DataResult
from ..guardrails import PIIAgent, SafetyAgent, SafetySignal
from ..rag.schemas import RagResult
from ..rag.service import RagAgent
from ..router.agent import RouterAgent
from ..triage.agent import TriageAgent
from ..triage.schemas import Entities
from .input import prepare_question
from .response import compose_result
from .schemas import WorkflowState

logger = logging.getLogger(__name__)


class WorkflowNodes:
    def __init__(self, triage: TriageAgent, router: RouterAgent, rag: RagAgent, data: DataAgent):
        self.triage, self.router, self.rag, self.data = triage, router, rag, data

    def pii_agent(self, state: WorkflowState):
        question = state["question"]
        if not isinstance(question, str) or not question.strip() or len(question) > 4000:
            raise ValueError("Question must contain 1 to 4000 characters.")
        result = PIIAgent().sanitize(question.strip())
        return {"question": result.sanitized_text, "pii_result": result}

    def safety_agent(self, state: WorkflowState):
        return {"safety_result": SafetyAgent().evaluate(state["pii_result"])}

    def triage_agent(self, state: WorkflowState, config: RunnableConfig):
        question = prepare_question(state["question"])
        try:
            result = self.triage.invoke(question, config)
            result = result.model_copy(
                update={
                    "summary": prepare_question(result.summary),
                    "missing_information": [
                        PIIAgent().sanitize(item).sanitized_text
                        for item in result.missing_information
                    ],
                }
            )
            if not SafetyAgent().evaluate(PIIAgent().sanitize(result.summary)).allowed:
                raise ValueError("Unsafe triage summary")
            if state.get("entity_context"):
                entities = {**result.entities.model_dump(), **state["entity_context"]}
                result = result.model_copy(update={"entities": Entities.model_validate(entities)})
            if state["safety_result"].priority_override:
                result = result.model_copy(update={"priority": "P1"})
                if SafetySignal.URGENT_SAFETY in state["safety_result"].signals:
                    result = result.model_copy(
                        update={"intent": "incident", "category": "Product Quality and Safety"}
                    )
            if re.search(
                r"\ball registers\b[^.!?\n]{0,100}\b(?:down|fail\w*|cannot|unable)\b",
                question,
                re.I,
            ):
                result = result.model_copy(
                    update={"priority": "P1", "intent": "incident", "category": "POS and Payments"}
                )
            return {"question": question, "triage_result": result}
        except Exception as exc:
            logger.warning("Triage failed (%s)", type(exc).__name__)
            return {
                "question": question,
                "error": "Triage is unavailable. Please retry or seek review.",
            }

    def router_agent(self, state: WorkflowState, config: RunnableConfig):
        try:
            decision = self.router.invoke(state["triage_result"], config)
            clean = {
                key: PIIAgent().sanitize(value).sanitized_text
                for key, value in decision.model_dump().items()
                if isinstance(value, str)
            }
            return {"route_decision": decision.model_copy(update=clean)}
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
            question = prepare_question(question)
            if not SafetyAgent().evaluate(PIIAgent().sanitize(question)).allowed:
                return {
                    "rag_result": RagResult(
                        status="invalid_response",
                        answer="Policy routing failed safety validation. Please seek review.",
                    )
                }
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
        try:
            result = self.data.invoke(
                state["question"],
                state["route_decision"],
                state["triage_result"],
                state.get("viewer_employee_id"),
                config,
            )
        except Exception as exc:
            logger.warning("Data specialist failed (%s)", type(exc).__name__)
            result = DataResult(status="unavailable", summary="Operational data is unavailable.")
        return {"data_result": result}

    def compose(self, state: WorkflowState):
        return {"result": compose_result(state)}
