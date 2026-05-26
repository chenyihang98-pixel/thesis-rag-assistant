"""Embedding provider factory."""

from __future__ import annotations

from thesis_agent.embeddings.hash import HashEmbeddingProvider
from thesis_agent.embeddings.sentence_transformer import SentenceTransformerEmbeddingProvider


def get_embedding_provider(name: str = "hash", *, model_name: str = ""):
    normalized = (name or "hash").strip().lower()
    if normalized == "hash":
        return HashEmbeddingProvider()
    if normalized in {"sentence-transformer", "sentence_transformer", "sentence-transformers"}:
        return SentenceTransformerEmbeddingProvider(model_name or "sentence-transformers/paraphrase-multilingual-MiniLM-L12-v2")
    raise ValueError(f"Unsupported embedding provider: {name}")
