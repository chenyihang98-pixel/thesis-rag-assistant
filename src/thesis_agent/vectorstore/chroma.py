"""Lightweight Chroma-style local vector index.

The implementation persists a deterministic hash index as JSONL so tests and
demo scripts do not need a running service or downloaded embedding model.
"""

from __future__ import annotations

import json
import shutil
from pathlib import Path

from thesis_agent.embeddings.hash import HashEmbeddingProvider, cosine_similarity
from thesis_agent.retrieval.io import load_chunks_jsonl, save_jsonl
from thesis_agent.retrieval.models import SearchResult


INDEX_FILE = "hash_vector_index.jsonl"
MANIFEST_FILE = "vector_index_manifest.json"


def _chunk_text_for_embedding(chunk: dict) -> str:
    return chunk.get("embedding_text") or chunk.get("display_text") or chunk.get("text", "")


def build_vector_index(
    *,
    chunks_path: Path,
    persist_dir: Path,
    collection_name: str = "thesis_agent_demo",
    embedding_provider_name: str = "hash",
    embedding_model: str = "",
    reset: bool = False,
) -> dict:
    if embedding_provider_name != "hash":
        raise ValueError("Only the offline hash embedding provider is available in tests by default")
    if reset and persist_dir.exists():
        shutil.rmtree(persist_dir)
    persist_dir.mkdir(parents=True, exist_ok=True)
    chunks = load_chunks_jsonl(chunks_path)
    embedder = HashEmbeddingProvider()
    records: list[dict] = []
    for chunk in chunks:
        records.append(
            {
                "chunk": chunk,
                "embedding": embedder.embed_text(_chunk_text_for_embedding(chunk)),
            }
        )
    save_jsonl(records, persist_dir / INDEX_FILE)
    manifest = {
        "collection_name": collection_name,
        "chunk_count": len(records),
        "embedding_provider": embedding_provider_name,
        "model_name": embedding_model,
        "index_file": INDEX_FILE,
    }
    (persist_dir / MANIFEST_FILE).write_text(json.dumps(manifest, ensure_ascii=False, indent=2), encoding="utf-8")
    return {"chunk_count": len(records), "collection_count": len(records), "collection_name": collection_name, "persist_dir": persist_dir.as_posix(), "embedding_provider": embedding_provider_name, "model_name": embedding_model, "reset": reset}


def _load_vector_records(persist_dir: Path) -> list[dict]:
    path = persist_dir / INDEX_FILE
    if not path.exists():
        raise ValueError(f"Vector index file does not exist: {path}")
    records: list[dict] = []
    with path.open("r", encoding="utf-8") as handle:
        for line in handle:
            stripped = line.strip()
            if stripped:
                records.append(json.loads(stripped))
    if not records:
        raise ValueError("Vector index is empty")
    return records


def search_vector_index(
    *,
    persist_dir: Path,
    query: str,
    top_k: int = 5,
    collection_name: str = "thesis_agent_demo",
    embedding_provider_name: str = "hash",
) -> list[SearchResult]:
    del collection_name
    if embedding_provider_name != "hash":
        raise ValueError("Only the offline hash embedding provider is available in tests by default")
    query_vector = HashEmbeddingProvider().embed_text(query)
    ranked = []
    for record in _load_vector_records(persist_dir):
        score = cosine_similarity(query_vector, record["embedding"])
        ranked.append((score, record["chunk"]))
    ranked.sort(key=lambda item: item[0], reverse=True)
    results: list[SearchResult] = []
    for rank, (score, chunk) in enumerate(ranked[:top_k], start=1):
        metadata = chunk.get("metadata", {})
        results.append(
            SearchResult(
                rank=rank,
                score=float(score),
                chunk_id=chunk["chunk_id"],
                doc_id=chunk["doc_id"],
                title=chunk["title"],
                text=chunk.get("display_text") or chunk.get("text", ""),
                metadata=metadata,
                citation=chunk.get("citation") or metadata.get("citation") or f"{chunk['doc_id']}#{chunk['chunk_id']}",
            )
        )
    return results
