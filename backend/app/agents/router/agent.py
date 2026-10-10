from langchain_core.runnables import Runnable, RunnableConfig

from ..triage.schemas import TriageResult
from .prompts import ROUTER_PROMPT
from .schemas import RouteDecision


class RouterAgent:
    def __init__(self, model: Runnable):
        self.chain = ROUTER_PROMPT | model

    def invoke(self, triage: TriageResult, config: RunnableConfig | None = None) -> RouteDecision:
        if triage.restricted_request or triage.intent == "unsupported":
            return RouteDecision(route="refuse", reason="Unsupported or restricted request.")
        decision = RouteDecision.model_validate(
            self.chain.invoke(
                {"triage": triage.model_dump_json()},
                config=config,
            )
        )
        # Enforce the evidence contract even when the model under-routes advice.
        if triage.intent in {"incident", "recommendation", "policy_question"}:
            if decision.route == "data":
                decision = decision.model_copy(update={"route": "both"})
            if triage.priority == "P1" and decision.route == "clarify":
                decision = RouteDecision(route="rag", reason="Urgent policy guidance first.")
        return decision
