"""LangChain runnable composition: context formatting -> prompt -> structured model."""

import json

from langchain_core.runnables import Runnable, RunnableLambda

from .prompts import ANSWER_PROMPT


def format_context(inputs: dict) -> dict[str, str]:
    return {
        "question": inputs["question"],
        "context": json.dumps(
            [
                {"section_id": section.section_id, "heading": section.heading, "text": section.text}
                for section in inputs["sections"]
            ]
        ),
    }


def build_answer_chain(model: Runnable) -> Runnable:
    return RunnableLambda(format_context) | ANSWER_PROMPT | model
