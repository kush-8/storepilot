"""Public evidence/result contracts and the constrained model response."""

from typing import Literal

from langchain_core.documents import Document
from pydantic import BaseModel, ConfigDict, Field


class PolicySection(BaseModel):
    model_config = ConfigDict(frozen=True)

    section_id: str
    source_id: str
    filename: str
    title: str
    heading: str
    heading_slug: str
    line_start: int
    line_end: int
    source_hash: str
    text: str
    parent_section_id: str | None = None
    chunk_index: int = 0
    chunk_count: int = 1
    chunk_start: int = 0
    chunk_end: int | None = None

    @classmethod
    def from_document(cls, document: Document):
        return cls(**document.metadata, text=document.page_content)


class RetrievedSection(PolicySection):
    distance: float


class GroundedStatement(BaseModel):
    model_config = ConfigDict(extra="forbid")

    text: str = Field(min_length=1, max_length=2000)
    citation_ids: list[str] = Field(min_length=1, max_length=4)


class GeneratedAnswer(BaseModel):
    """Every answer statement must identify supporting retrieved sections."""

    model_config = ConfigDict(extra="forbid")

    insufficient_evidence: bool
    statements: list[GroundedStatement] = Field(max_length=8)


class RagResult(BaseModel):
    status: Literal["answered", "insufficient_evidence", "invalid_response", "model_unavailable"]
    answer: str
    citations: list[RetrievedSection] = Field(default_factory=list)
    retrieved_sections: list[RetrievedSection] = Field(default_factory=list)
