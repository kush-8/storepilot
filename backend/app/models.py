"""Validated client inputs. Server-derived identity and classification cannot be supplied."""

from datetime import datetime
from typing import Literal
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field, model_validator

StoreID = str
Category = Literal[
    "POS and Payments",
    "Inventory and Replenishment",
    "Pricing and Promotions",
    "Returns and Refunds",
    "Vendor and Supply Chain",
    "Product Quality and Safety",
    "Customer Service",
    "Other or Security",
]
Status = Literal["Open", "In Progress", "Closed"]
Priority = Literal["P1", "P2", "P3", "P4"]


class Input(BaseModel):
    model_config = ConfigDict(extra="forbid", str_strip_whitespace=True)


class LoginRequest(Input):
    employee_id: str = Field(pattern=r"^E[0-9]{4}$")
    store_id: str = Field(pattern=r"^(ST[0-9]{3}|WH[0-9]{3})$")


class ConversationCreate(Input):
    affected_store_id: str | None = Field(default=None, pattern=r"^(ST[0-9]{3}|WH[0-9]{3})$")


class MessageContext(ConversationCreate):
    sku: str | None = Field(default=None, pattern=r"^SKU[0-9]+$")
    register_id: str | None = Field(default=None, min_length=1, max_length=80)


class MessageRequest(Input):
    content: str = Field(min_length=1, max_length=4000)
    client_message_id: UUID
    context: MessageContext = Field(default_factory=MessageContext)


class TicketCreate(Input):
    draft_id: UUID
    draft_revision: int = Field(ge=1)


class StatusUpdate(Input):
    status: Status
    expected_version: int = Field(ge=1)
    reason: str | None = Field(default=None, min_length=1, max_length=1000)


class Filters(Input):
    data_mode: Literal["live", "historical_snapshot"] = "live"
    window: Literal["last24h", "last7d", "last30d", "all"] | None = None
    store_id: str | None = Field(default=None, pattern=r"^(ST[0-9]{3}|WH[0-9]{3})$")
    sku: str | None = Field(default=None, pattern=r"^SKU[0-9]+$")
    status: Status | None = None
    priority: Priority | None = None
    category: Category | None = None
    start: datetime | None = None
    end: datetime | None = None

    @model_validator(mode="after")
    def valid_range(self):
        if bool(self.start) != bool(self.end):
            raise ValueError("Provide start and end together")
        if self.start:
            if self.window:
                raise ValueError("Custom dates cannot be combined with window")
            if self.start.tzinfo is None or self.end.tzinfo is None:
                raise ValueError("Dates must contain a timezone")
            if self.start >= self.end:
                raise ValueError("start must precede end")
            anchor = datetime.fromisoformat("2026-10-10T12:00:00+05:30")
            if self.data_mode == "historical_snapshot" and self.end > anchor:
                raise ValueError("Historical end exceeds event anchor")
        return self


class AnalyticsRequest(Input):
    question: str = Field(min_length=1, max_length=4000)
    filters: Filters = Field(default_factory=Filters)
    analytics_thread_id: UUID | None = None
