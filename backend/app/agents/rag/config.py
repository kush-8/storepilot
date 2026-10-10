"""Explicit configuration, independent of app.main and the working directory."""

import os
from pathlib import Path

from dotenv import load_dotenv
from pydantic import BaseModel, ConfigDict, Field, SecretStr

BACKEND_ROOT = Path(__file__).resolve().parents[3]


class RagSettings(BaseModel):
    model_config = ConfigDict(frozen=True)

    knowledge_base_path: Path = BACKEND_ROOT / "knowledge_base"
    chroma_path: Path = BACKEND_ROOT / ".cache/chroma"
    embedding_cache_path: Path = BACKEND_ROOT / ".cache/embeddings"
    collection_prefix: str = Field(default="storepilot-policies", pattern=r"^[a-zA-Z0-9-]{3,50}$")
    groq_api_key: SecretStr | None = Field(default=None, repr=False, exclude=True)
    groq_model: str = Field(default="openai/gpt-oss-120b", min_length=1)
    top_k: int = Field(default=4, ge=1, le=4)
    max_distance: float = Field(default=0.65, ge=0, le=2, allow_inf_nan=False)
    timeout_seconds: float = Field(default=30, gt=0, le=120, allow_inf_nan=False)

    @classmethod
    def from_env(cls) -> "RagSettings":
        load_dotenv(BACKEND_ROOT / ".env", override=False)

        def path(name: str, default: str) -> Path:
            value = Path(os.getenv(name, default)).expanduser()
            return value if value.is_absolute() else BACKEND_ROOT / value

        return cls(
            knowledge_base_path=path("RAG_KNOWLEDGE_BASE_PATH", "knowledge_base"),
            chroma_path=path("RAG_CHROMA_PATH", ".cache/chroma"),
            embedding_cache_path=path("RAG_EMBEDDING_CACHE_PATH", ".cache/embeddings"),
            collection_prefix=os.getenv("RAG_COLLECTION_PREFIX", "storepilot-policies"),
            groq_api_key=os.getenv("GROQ_API_KEY") or None,
            groq_model=os.getenv("GROQ_MODEL", "openai/gpt-oss-120b"),
            top_k=os.getenv("RAG_TOP_K", "4"),
            max_distance=os.getenv("RAG_MAX_DISTANCE", "0.65"),
            timeout_seconds=os.getenv("MODEL_TIMEOUT_SECONDS", "30"),
        )
