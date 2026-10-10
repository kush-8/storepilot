"""Chroma persistence lifecycle; document writes/searches use LangChain Chroma."""

import chromadb
from chromadb.config import Settings
from chromadb.errors import NotFoundError
from langchain_chroma import Chroma
from langchain_core.embeddings import Embeddings

from ..config import RagSettings


class IndexNotReadyError(RuntimeError):
    """An explicit indexing job is required for the current policy version."""


class PolicyVectorStore:
    def __init__(self, settings: RagSettings, embeddings: Embeddings):
        self.settings = settings
        self.embeddings = embeddings

    def _client(self):
        return chromadb.PersistentClient(
            path=str(self.settings.chroma_path),
            settings=Settings(anonymized_telemetry=False),
        )

    def is_ready(self, name: str, count: int) -> bool:
        if not self.settings.chroma_path.exists():
            return False
        try:
            collection = self._client().get_collection(name, embedding_function=None)
        except NotFoundError:
            return False
        return bool((collection.metadata or {}).get("ready")) and collection.count() == count

    def open(self, name: str, count: int) -> Chroma:
        if not self.is_ready(name, count):
            raise IndexNotReadyError(
                "Policy index is missing, stale or incomplete. "
                "Run `python -m app.agents.rag index`."
            )
        return Chroma(
            client=self._client(),
            collection_name=name,
            embedding_function=self.embeddings,
            create_collection_if_not_exists=False,
        )

    def create(self, name: str, embedding_id: str) -> Chroma:
        client = self._client()
        collection = client.get_or_create_collection(
            name,
            embedding_function=None,
            metadata={"ready": False, "embedding": embedding_id},
            configuration={"hnsw": {"space": "cosine"}},
        )
        collection.modify(metadata={"ready": False, "embedding": embedding_id})
        return Chroma(
            client=client,
            collection_name=name,
            embedding_function=self.embeddings,
            create_collection_if_not_exists=False,
        )

    def publish(self, name: str, embedding_id: str) -> None:
        self._client().get_collection(name, embedding_function=None).modify(
            metadata={"ready": True, "embedding": embedding_id},
        )
