"""Policy document loading and Markdown section splitting."""

from pathlib import Path

from langchain_core.documents import Document

from .loader import PolicyMarkdownLoader
from .splitter import PolicySectionSplitter


def load_policy_documents(directory: Path) -> list[Document]:
    return list(PolicySectionSplitter().transform_documents(PolicyMarkdownLoader(directory).load()))
