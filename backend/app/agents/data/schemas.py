from typing import Literal

from pydantic import BaseModel, ConfigDict, Field, model_validator

from ..router.schemas import QueryName


class DataEvidence(BaseModel):
    evidence_id: str
    query: QueryName
    rows: list[dict[str, str | int | float | None]]
    truncated: bool = False
    window_start: str | None = None
    window_end: str | None = None
    dataset: str = "historical_retail_snapshot"
    sql: str


class GeneratedSqlQuery(BaseModel):
    model_config = ConfigDict(extra="forbid")

    evidence_type: QueryName
    sql: str = Field(min_length=1, max_length=5000)


class GeneratedSqlPlan(BaseModel):
    model_config = ConfigDict(extra="forbid")

    queries: list[GeneratedSqlQuery] = Field(min_length=1, max_length=3)

    @model_validator(mode="after")
    def unique_evidence_types(self):
        types = [query.evidence_type for query in self.queries]
        if len(types) != len(set(types)):
            raise ValueError("Generate one SQL query per evidence type.")
        return self


class DataResult(BaseModel):
    status: Literal[
        "answered",
        "no_data",
        "needs_clarification",
        "forbidden",
        "unavailable",
        "invalid_query",
        "model_unavailable",
    ]
    summary: str
    evidence: list[DataEvidence] = Field(default_factory=list)
