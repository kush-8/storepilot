"""LangChain Embeddings adapter for the existing lightweight local ONNX model."""

from langchain_core.embeddings import Embeddings

from ..config import RagSettings


class LocalEmbeddings(Embeddings):
    fingerprint = "onnx-all-MiniLM-L6-v2:384:normalized:mean-pooling:v1"

    def __init__(self, settings: RagSettings):
        from chromadb.utils.embedding_functions import ONNXMiniLM_L6_V2

        self._encoder = ONNXMiniLM_L6_V2(preferred_providers=["CPUExecutionProvider"])
        self._encoder.DOWNLOAD_PATH = settings.embedding_cache_path / "all-MiniLM-L6-v2"

    def embed_documents(self, texts: list[str]) -> list[list[float]]:
        return [vector.tolist() for vector in self._encoder(texts)]

    def embed_query(self, text: str) -> list[float]:
        return self.embed_documents([text])[0]
