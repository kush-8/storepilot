"""LangChain retriever with cosine cutoff and authoritative source resolution."""

from langchain_core.callbacks import CallbackManagerForRetrieverRun
from langchain_core.documents import Document
from langchain_core.retrievers import BaseRetriever

from .index import PolicyIndex


class PolicyRetriever(BaseRetriever):
    index: PolicyIndex

    def _get_relevant_documents(
        self,
        query: str,
        *,
        run_manager: CallbackManagerForRetrieverRun,
    ) -> list[Document]:
        if not query.strip() or len(query) > 4000:
            raise ValueError("Question must contain 1 to 4000 characters.")
        documents, name = self.index.snapshot()
        store = self.index.store.open(name, len(documents))
        matches = store.similarity_search_with_score(
            query,
            k=min(self.index.settings.top_k, len(documents)),
        )
        by_id = {doc.id: doc for doc in documents}
        results = []
        for match, distance in matches:
            section_id = match.metadata.get("section_id")
            if section_id in by_id and distance <= self.index.settings.max_distance:
                source = by_id[section_id]
                results.append(
                    Document(
                        id=source.id,
                        page_content=source.page_content,
                        metadata={**source.metadata, "distance": float(distance)},
                    )
                )
        return results
