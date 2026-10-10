"""LangChain loader for the policy directory, preserving original source provenance."""

import hashlib
from collections.abc import Iterator
from pathlib import Path

from langchain_core.document_loaders import BaseLoader
from langchain_core.documents import Document


class PolicyMarkdownLoader(BaseLoader):
    def __init__(self, directory: Path):
        self.directory = directory

    def lazy_load(self) -> Iterator[Document]:
        files = sorted(self.directory.glob("*.md"))
        if not files:
            raise ValueError(f"No Markdown policies found in {self.directory}")
        for path in files:
            if path.is_symlink():
                raise ValueError(f"Policy symlinks are not supported: {path.name}")
            raw = path.read_bytes()
            yield Document(
                page_content=raw.decode("utf-8-sig"),
                metadata={
                    "source": str(path),
                    "filename": path.name,
                    "source_hash": hashlib.sha256(raw).hexdigest(),
                },
            )
