"""Retriever provider interfaces."""

from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path
from typing import Protocol

from thesis_agent.retrieval.models import SearchResult


@dataclass
class RetrievalResponse:
    query: str
    results: list[SearchResult]
    provider: str
    metadata: dict = field(default_factory=dict)


class RetrieverProvider(Protocol):
    provider_name: str

    def search(self, query: str, top_k: int = 5) -> RetrievalResponse:
        ...


@dataclass
class RetrieverConfig:
    provider_name: str = "tfidf"
    index_path: Path | None = None
    vector_persist_dir: Path | None = None
    vector_collection: str = "thesis_agent_demo"
    embedding_provider: str = "hash"
