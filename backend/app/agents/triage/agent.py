"""LangChain triage chain with explicit-ID grounding."""

import re

from langchain_core.runnables import Runnable, RunnableConfig

from .prompts import TRIAGE_PROMPT
from .schemas import TriageResult


class TriageAgent:
    def __init__(self, model: Runnable):
        self.chain = TRIAGE_PROMPT | model

    def invoke(self, question: str, config: RunnableConfig | None = None) -> TriageResult:
        result = TriageResult.model_validate(
            self.chain.invoke({"question": question}, config=config)
        )
        entities = result.entities.model_dump()
        for key, value in entities.items():
            if value and not re.search(rf"(?<![\w-]){re.escape(value)}(?![\w-])", question, re.I):
                entities[key] = None
            elif value:
                entities[key] = value.upper()
        return result.model_copy(update={"entities": result.entities.model_validate(entities)})
