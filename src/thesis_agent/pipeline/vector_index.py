"""Pipeline wrapper for building and searching the local vector index."""

from thesis_agent.vectorstore.chroma import build_vector_index, search_vector_index

__all__ = ["build_vector_index", "search_vector_index"]
