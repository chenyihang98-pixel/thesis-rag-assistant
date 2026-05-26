"""本地 TF-IDF 检索流程辅助模块。"""

from __future__ import annotations

from pathlib import Path

from thesis_agent.language import normalize_document_language
from thesis_agent.retrieval.io import load_chunks_jsonl
from thesis_agent.retrieval.models import RetrievalConfig, SearchResult
from thesis_agent.retrieval.tfidf import TfidfRetriever
from thesis_agent.vectorstore.chroma import search_vector_index as _search_vector_index


def build_tfidf_index(
    chunks_path: Path,
    index_output: Path,
    language: str = "ja",
    analyzer: str = "char",
    ngram_min: int = 2,
    ngram_max: int = 5,
) -> dict:
    """Build and persist a local TF-IDF index from chunk JSONL."""
    chunks = load_chunks_jsonl(chunks_path)
    config = RetrievalConfig(
        analyzer=analyzer,
        ngram_min=ngram_min,
        ngram_max=ngram_max,
        language=normalize_document_language(language),
    )

    retriever = TfidfRetriever(config=config).fit(chunks)
    retriever.save(index_output)

    return {
        "chunk_count": len(chunks),
        "index_output": index_output.as_posix(),
        "analyzer": analyzer,
        "ngram_range": (ngram_min, ngram_max),
        "language": config.language,
    }


def search_tfidf_index(
    index_path: Path,
    query: str,
    top_k: int = 5,
) -> list[SearchResult]:
    """Search a persisted local TF-IDF index."""
    retriever = TfidfRetriever.load(index_path)
    return retriever.search(query=query, top_k=top_k)


def search_vector_index(
    persist_dir: Path,
    query: str,
    top_k: int = 5,
    collection_name: str = "thesis_agent_demo",
    embedding_provider_name: str = "hash",
) -> list[SearchResult]:
    """Search the local hash vector index."""
    return _search_vector_index(
        persist_dir=persist_dir,
        query=query,
        top_k=top_k,
        collection_name=collection_name,
        embedding_provider_name=embedding_provider_name,
    )


def search_hybrid_index(
    *,
    tfidf_index_path: Path,
    vector_persist_dir: Path,
    query: str,
    top_k: int = 5,
    vector_collection: str = "thesis_agent_demo",
    embedding_provider_name: str = "hash",
    tfidf_weight: float = 0.5,
    vector_weight: float = 0.5,
) -> list[SearchResult]:
    """Merge TF-IDF and vector results with a simple weighted score."""
    tfidf_results = search_tfidf_index(tfidf_index_path, query=query, top_k=top_k * 2)
    vector_results = search_vector_index(
        vector_persist_dir,
        query=query,
        top_k=top_k * 2,
        collection_name=vector_collection,
        embedding_provider_name=embedding_provider_name,
    )
    by_citation: dict[str, tuple[SearchResult, float]] = {}
    for result in tfidf_results:
        by_citation[result.citation] = (result, by_citation.get(result.citation, (result, 0.0))[1] + tfidf_weight * result.score)
    for result in vector_results:
        existing = by_citation.get(result.citation, (result, 0.0))
        by_citation[result.citation] = (existing[0], existing[1] + vector_weight * result.score)
    ranked = sorted(by_citation.values(), key=lambda item: item[1], reverse=True)[:top_k]
    merged: list[SearchResult] = []
    for rank, (result, score) in enumerate(ranked, start=1):
        merged.append(
            SearchResult(
                rank=rank,
                score=float(score),
                chunk_id=result.chunk_id,
                doc_id=result.doc_id,
                title=result.title,
                text=result.text,
                metadata={**result.metadata, "hybrid_score": float(score)},
                citation=result.citation,
            )
        )
    return merged
