"""TF-IDF retriever provider wrapper."""

from __future__ import annotations

from pathlib import Path

from thesis_agent.pipeline.retrieval import search_tfidf_index
from thesis_agent.retrieval.base import RetrievalResponse


class TfidfRetrieverProvider:
    provider_name = "tfidf"

    def __init__(self, index_path: Path) -> None:
        self.index_path = index_path

    def search(self, query: str, top_k: int = 5) -> RetrievalResponse:
        return RetrievalResponse(query=query, results=search_tfidf_index(self.index_path, query, top_k=top_k), provider=self.provider_name)
