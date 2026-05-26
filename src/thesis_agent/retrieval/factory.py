"""Retriever provider factory."""

from __future__ import annotations

from pathlib import Path

from thesis_agent.retrieval.hybrid_provider import HybridRetrieverProvider
from thesis_agent.retrieval.tfidf_provider import TfidfRetrieverProvider
from thesis_agent.retrieval.vector_provider import VectorRetrieverProvider


def get_retriever_provider(name: str = "tfidf", **kwargs):
    normalized = (name or "tfidf").lower()
    if normalized == "tfidf":
        return TfidfRetrieverProvider(Path(kwargs["index_path"]))
    if normalized == "vector":
        return VectorRetrieverProvider(
            persist_dir=Path(kwargs["vector_persist_dir"]),
            collection_name=kwargs.get("vector_collection", "thesis_agent_demo"),
            embedding_provider=kwargs.get("embedding_provider", "hash"),
        )
    if normalized == "hybrid":
        return HybridRetrieverProvider(
            index_path=Path(kwargs["index_path"]),
            vector_persist_dir=Path(kwargs["vector_persist_dir"]),
            collection_name=kwargs.get("vector_collection", "thesis_agent_demo"),
            embedding_provider=kwargs.get("embedding_provider", "hash"),
        )
    raise ValueError(f"Unsupported retriever provider: {name}")
