"""Vector retriever provider wrapper."""

from __future__ import annotations

from pathlib import Path

from thesis_agent.pipeline.retrieval import search_vector_index
from thesis_agent.retrieval.base import RetrievalResponse


class VectorRetrieverProvider:
    provider_name = "vector"

    def __init__(self, persist_dir: Path, collection_name: str = "thesis_agent_demo", embedding_provider: str = "hash") -> None:
        self.persist_dir = persist_dir
        self.collection_name = collection_name
        self.embedding_provider = embedding_provider

    def search(self, query: str, top_k: int = 5) -> RetrievalResponse:
        return RetrievalResponse(
            query=query,
            results=search_vector_index(self.persist_dir, query, top_k=top_k, collection_name=self.collection_name, embedding_provider_name=self.embedding_provider),
            provider=self.provider_name,
        )
