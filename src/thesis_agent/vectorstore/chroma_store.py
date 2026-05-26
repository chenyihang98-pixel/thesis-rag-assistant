"""Compatibility exports for the local Chroma store surface."""

from thesis_agent.vectorstore.chroma import (
    INDEX_FILE,
    MANIFEST_FILE,
    build_vector_index,
    search_vector_index,
)

__all__ = ["INDEX_FILE", "MANIFEST_FILE", "build_vector_index", "search_vector_index"]
