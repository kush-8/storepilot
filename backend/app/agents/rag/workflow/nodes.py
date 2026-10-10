"""Thin LangGraph node adapters over LangChain retrieval/generation and validation."""

import logging

from langchain_core.exceptions import OutputParserException
from langchain_core.runnables import Runnable, RunnableConfig
from pydantic import ValidationError

from ..generation.validation import abstention, validate_answer
from ..schemas import GeneratedAnswer, RagResult, RetrievedSection
from .state import RagState

logger = logging.getLogger(__name__)


class RagNodes:
    def __init__(self, retriever: Runnable, answer_chain: Runnable):
        self.retriever = retriever
        self.answer_chain = answer_chain

    def retrieve(self, state: RagState, config: RunnableConfig):
        question = state["question"].strip()
        if not question or len(question) > 4000:
            raise ValueError("Question must contain 1 to 4000 characters.")
        documents = self.retriever.invoke(question, config=config)
        return {
            "question": question,
            "sections": [RetrievedSection.from_document(doc) for doc in documents],
        }

    def generate(self, state: RagState, config: RunnableConfig):
        try:
            draft = self.answer_chain.invoke(
                {"question": state["question"], "sections": state["sections"]},
                config=config,
            )
            return {"draft": GeneratedAnswer.model_validate(draft)}
        except (ValidationError, OutputParserException):
            status = "invalid_response"
            answer = "The model response could not be validated. Please seek human review."
        except Exception as exc:
            logger.warning("RAG model call failed (%s)", type(exc).__name__)
            status = "model_unavailable"
            answer = "The answer service is unavailable. Please retry or seek human review."
        return {
            "result": RagResult(
                status=status,
                answer=answer,
                retrieved_sections=state["sections"],
            )
        }

    def validate(self, state: RagState):
        if "result" in state:
            return {}
        return {"result": validate_answer(state["draft"], state["sections"])}

    def abstain(self, state: RagState):
        return {"result": abstention(state["sections"])}
