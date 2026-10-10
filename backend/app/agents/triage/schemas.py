"""Triage is a provisional interpretation, not operational approval."""

from typing import Annotated, Literal

from pydantic import BaseModel, ConfigDict, Field

Identifier = Annotated[str, Field(pattern=r"^[A-Za-z0-9_-]{1,64}$")]


class Entities(BaseModel):
    model_config = ConfigDict(extra="forbid")
    store_id: Identifier | None = None
    sku: Identifier | None = None
    vendor_id: Identifier | None = None


class TriageResult(BaseModel):
    model_config = ConfigDict(extra="forbid")

    summary: str = Field(min_length=1, max_length=1000)
    intent: Literal["policy_question", "data_question", "recommendation", "incident", "unsupported"]
    category: Literal[
        "POS and Payments",
        "Inventory and Replenishment",
        "Pricing and Promotions",
        "Returns and Refunds",
        "Vendor and Supply Chain",
        "Product Quality and Safety",
        "Customer Service",
        "Other or Security",
    ]
    priority: Literal["P1", "P2", "P3", "P4"]
    confidence: float = Field(ge=0, le=1, allow_inf_nan=False)
    entities: Entities = Field(default_factory=Entities)
    missing_information: list[str] = Field(default_factory=list, max_length=5)
    restricted_request: bool = False
