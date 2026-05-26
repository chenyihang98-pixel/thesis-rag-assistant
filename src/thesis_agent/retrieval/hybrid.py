"""Hybrid retrieval utilities."""

from __future__ import annotations

from thesis_agent.retrieval.models import SearchResult


def merge_weighted_results(
    *,
    tfidf_results: list[SearchResult],
    vector_results: list[SearchResult],
    top_k: int = 5,
    tfidf_weight: float = 0.5,
    vector_weight: float = 0.5,
) -> list[SearchResult]:
    """Merge result lists by citation using weighted scores."""
    by_citation: dict[str, tuple[SearchResult, float]] = {}
    for result in tfidf_results:
        current = by_citation.get(result.citation, (result, 0.0))
        by_citation[result.citation] = (current[0], current[1] + result.score * tfidf_weight)
    for result in vector_results:
        current = by_citation.get(result.citation, (result, 0.0))
        by_citation[result.citation] = (current[0], current[1] + result.score * vector_weight)
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
