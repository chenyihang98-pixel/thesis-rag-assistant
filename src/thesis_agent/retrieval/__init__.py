"""Retrieval package exports with lazy imports to avoid circular startup."""

from __future__ import annotations

__all__ = [
    "RetrievalResponse",
    "RetrieverConfig",
    "get_retriever_provider",
    "TfidfRetrieverProvider",
    "VectorRetrieverProvider",
    "HybridRetrieverProvider",
]


def __getattr__(name: str):
    if name in {"RetrievalResponse", "RetrieverConfig"}:
        from thesis_agent.retrieval.base import RetrievalResponse, RetrieverConfig

        return {"RetrievalResponse": RetrievalResponse, "RetrieverConfig": RetrieverConfig}[name]
    if name == "get_retriever_provider":
        from thesis_agent.retrieval.factory import get_retriever_provider

        return get_retriever_provider
    if name == "TfidfRetrieverProvider":
        from thesis_agent.retrieval.tfidf_provider import TfidfRetrieverProvider

        return TfidfRetrieverProvider
    if name == "VectorRetrieverProvider":
        from thesis_agent.retrieval.vector_provider import VectorRetrieverProvider

        return VectorRetrieverProvider
    if name == "HybridRetrieverProvider":
        from thesis_agent.retrieval.hybrid_provider import HybridRetrieverProvider

        return HybridRetrieverProvider
    raise AttributeError(name)
