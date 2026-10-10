"""Explicit indexing service and source/configuration versioning."""

import hashlib
import json

from langchain_core.documents import Document
from langchain_core.embeddings import Embeddings

from ..config import RagSettings
from ..ingestion import load_policy_documents
from ..ingestion.splitter import PolicySectionSplitter
from ..schemas import RetrievedSection
from .embeddings import LocalEmbeddings
from .vector_store import IndexNotReadyError, PolicyVectorStore

__all__ = ["IndexNotReadyError", "PolicyIndex"]


class PolicyIndex:
    def __init__(
        self,
        settings: RagSettings,
        embeddings: Embeddings | None = None,
        *,
        embedding_id: str | None = None,
    ):
        self.settings = settings
        self.embeddings = embeddings if embeddings is not None else LocalEmbeddings(settings)
        self.embedding_id = embedding_id or getattr(self.embeddings, "fingerprint", None)
        if not self.embedding_id:
            raise ValueError("Supply embedding_id when injecting a LangChain embedding provider.")
        self.store = PolicyVectorStore(settings, self.embeddings)

    def snapshot(self) -> tuple[list[Document], str]:
        documents = load_policy_documents(self.settings.knowledge_base_path)
        manifest = {
            "parser": PolicySectionSplitter.fingerprint,
            "embedding": self.embedding_id,
            "metric": "cosine",
            "content": "title-heading-body-v1",
            "sections": [
                {
                    "text": doc.page_content,
                    "metadata": {
                        key: value for key, value in doc.metadata.items() if key != "source"
                    },
                }
                for doc in documents
            ],
        }
        digest = hashlib.sha256(json.dumps(manifest, sort_keys=True).encode()).hexdigest()
        return documents, f"{self.settings.collection_prefix}-{digest[:24]}"

    def build(self) -> dict[str, str | int]:
        documents, name = self.snapshot()
        if self.store.is_ready(name, len(documents)):
            return {"collection": name, "sections": len(documents), "status": "unchanged"}
        store = self.store.create(name, self.embedding_id)
        index_documents = [
            Document(
                id=doc.id,
                metadata=doc.metadata,
                page_content=f"{doc.metadata['title']}\n{doc.metadata['heading']}\n{doc.page_content}",
            )
            for doc in documents
        ]
        # LangChain invokes embed_documents and persists the Documents with stable IDs.
        store.add_documents(index_documents, ids=[doc.id for doc in documents])
        self.store.publish(name, self.embedding_id)
        return {"collection": name, "sections": len(documents), "status": "indexed"}

    def as_retriever(self):
        from .retriever import PolicyRetriever

        return PolicyRetriever(index=self)

    def search(self, question: str) -> list[RetrievedSection]:
        """Compatibility facade for CLI callers; retrieval runs through LangChain."""
        return [RetrievedSection.from_document(doc) for doc in self.as_retriever().invoke(question)]
