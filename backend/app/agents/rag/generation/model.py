"""Groq model construction, isolated from prompts and graph orchestration."""

from ...models import structured_model
from ..config import RagSettings
from ..schemas import GeneratedAnswer


def create_answer_model(settings: RagSettings):
    return structured_model(settings, GeneratedAnswer)
