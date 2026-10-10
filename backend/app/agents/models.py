"""Shared bounded Groq structured-model factory for specialist agents."""

from typing import TYPE_CHECKING

from langchain_groq import ChatGroq
from pydantic import BaseModel

if TYPE_CHECKING:
    from .rag.config import RagSettings


def structured_model(settings: "RagSettings", schema: type[BaseModel]):
    if not settings.groq_api_key or not settings.groq_api_key.get_secret_value().strip():
        raise ValueError("Set GROQ_API_KEY in backend/.env before running the agents.")
    model = ChatGroq(
        api_key=settings.groq_api_key,
        model=settings.groq_model,
        temperature=0,
        max_tokens=1800,
        timeout=settings.timeout_seconds,
        max_retries=1,
    )
    if settings.groq_model in {"openai/gpt-oss-120b", "openai/gpt-oss-20b"}:
        return model.with_structured_output(schema, method="json_schema", strict=True)
    return model.with_structured_output(schema, method="function_calling")
