from typing import Literal

from pydantic import BaseModel, ConfigDict, Field, model_validator

QueryName = Literal[
    "inventory", "product", "store", "receipts", "vendor", "returns", "case_summary"
]
Route = Literal["rag", "data", "both", "clarify", "refuse"]


class RouteDecision(BaseModel):
    model_config = ConfigDict(extra="forbid")
    route: Route
    reason: str = Field(min_length=1, max_length=600)
    queries: list[QueryName] = Field(default_factory=list, max_length=3)
    lookback_days: int = Field(default=30, ge=1, le=365)
    follow_up: str | None = Field(default=None, max_length=500)
    policy_question: str | None = Field(default=None, min_length=1, max_length=1500)

    @model_validator(mode="after")
    def consistent_plan(self):
        self.queries = list(dict.fromkeys(self.queries))
        if self.route in {"data", "both"} and not self.queries:
            raise ValueError("Data routes require at least one registered query.")
        if self.route in {"rag", "clarify", "refuse"} and self.queries:
            raise ValueError("Non-data routes cannot contain data queries.")
        if self.route == "clarify" and not self.follow_up:
            raise ValueError("Clarification requires a focused follow-up.")
        return self
