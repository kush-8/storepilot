"""Typed state for the standalone RAG workflow."""

from typing import TypedDict

from ..schemas import GeneratedAnswer, RagResult, RetrievedSection


class RagState(TypedDict, total=False):
    question: str
    sections: list[RetrievedSection]
    draft: GeneratedAnswer
    result: RagResult


class RagInput(TypedDict):
    question: str


class RagOutput(TypedDict):
    result: RagResult
