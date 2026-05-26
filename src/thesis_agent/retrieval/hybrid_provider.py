"""Hybrid retriever provider wrapper."""

from __future__ import annotations

from pathlib import Path

from thesis_agent.pipeline.retrieval import search_hybrid_index
from thesis_agent.retrieval.base import RetrievalResponse


class HybridRetrieverProvider:
    provider_name = "hybrid"

    def __init__(self, index_path: Path, vector_persist_dir: Path, collection_name: str = "thesis_agent_demo", embedding_provider: str = "hash") -> None:
        self.index_path = index_path
        self.vector_persist_dir = vector_persist_dir
        self.collection_name = collection_name
        self.embedding_provider = embedding_provider

    def search(self, query: str, top_k: int = 5) -> RetrievalResponse:
        return RetrievalResponse(
            query=query,
            results=search_hybrid_index(
                tfidf_index_path=self.index_path,
                vector_persist_dir=self.vector_persist_dir,
                query=query,
                top_k=top_k,
                vector_collection=self.collection_name,
                embedding_provider_name=self.embedding_provider,
            ),
            provider=self.provider_name,
        )
