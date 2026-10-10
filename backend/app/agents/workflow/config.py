import os
from datetime import datetime
from pathlib import Path

from pydantic import BaseModel, Field, field_validator

from ..rag.config import BACKEND_ROOT, RagSettings


class WorkflowSettings(BaseModel):
    rag: RagSettings = Field(default_factory=RagSettings)
    database_path: Path = BACKEND_ROOT / "database/retail.db"
    event_anchor: datetime = datetime.fromisoformat("2026-10-10T12:00:00+05:30")
    row_limit: int = Field(default=50, ge=1, le=100)

    @field_validator("event_anchor")
    @classmethod
    def require_timezone(cls, value: datetime) -> datetime:
        if value.utcoffset() is None:
            raise ValueError("EVENT_ANCHOR requires a timezone.")
        return value

    @classmethod
    def from_env(cls):
        rag = RagSettings.from_env()
        path = Path(os.getenv("DATABASE_PATH", "database/retail.db"))
        return cls(
            rag=rag,
            database_path=path if path.is_absolute() else BACKEND_ROOT / path,
            event_anchor=os.getenv("EVENT_ANCHOR", "2026-10-10T12:00:00+05:30"),
            row_limit=os.getenv("DATA_ROW_LIMIT", "50"),
        )
