"""Compare TF-IDF, vector, and hybrid retrieval modes."""

from __future__ import annotations

import json
from dataclasses import asdict, dataclass, field
from pathlib import Path

from thesis_agent.evaluation.chunk_eval import RetrievalComparisonQuery, load_retrieval_comparison_queries
from thesis_agent.pipeline.retrieval import search_hybrid_index, search_tfidf_index, search_vector_index


@dataclass
class RetrievalModeEvalResult:
    query: str
    tfidf_doc_ids: list[str]
    vector_doc_ids: list[str]
    hybrid_doc_ids: list[str]
    hybrid_overlap_with_tfidf: float
    hybrid_overlap_with_vector: float
    warnings: list[str] = field(default_factory=list)


@dataclass
class RetrievalModeEvalSummary:
    total_cases: int
    results: list[RetrievalModeEvalResult]
    avg_hybrid_overlap_with_tfidf: float
    avg_hybrid_overlap_with_vector: float
    warnings: list[str] = field(default_factory=list)


def _overlap(left: list[str], right: list[str]) -> float:
    if not left and not right:
        return 1.0
    return len(set(left) & set(right)) / max(len(set(left) | set(right)), 1)


def evaluate_retrieval_modes(
    *,
    queries: list[RetrievalComparisonQuery],
    tfidf_index_path: Path,
    vector_persist_dir: Path,
    vector_collection: str = "thesis_agent_demo",
    embedding_provider: str = "hash",
) -> RetrievalModeEvalSummary:
    results: list[RetrievalModeEvalResult] = []
    for query in queries:
        tfidf = search_tfidf_index(tfidf_index_path, query.query, top_k=query.top_k)
        vector = search_vector_index(vector_persist_dir, query.query, top_k=query.top_k, collection_name=vector_collection, embedding_provider_name=embedding_provider)
        hybrid = search_hybrid_index(tfidf_index_path=tfidf_index_path, vector_persist_dir=vector_persist_dir, query=query.query, top_k=query.top_k, vector_collection=vector_collection, embedding_provider_name=embedding_provider)
        tfidf_ids = [item.doc_id for item in tfidf]
        vector_ids = [item.doc_id for item in vector]
        hybrid_ids = [item.doc_id for item in hybrid]
        results.append(RetrievalModeEvalResult(query=query.query, tfidf_doc_ids=tfidf_ids, vector_doc_ids=vector_ids, hybrid_doc_ids=hybrid_ids, hybrid_overlap_with_tfidf=_overlap(hybrid_ids, tfidf_ids), hybrid_overlap_with_vector=_overlap(hybrid_ids, vector_ids)))
    total = len(results)
    return RetrievalModeEvalSummary(total_cases=total, results=results, avg_hybrid_overlap_with_tfidf=sum(r.hybrid_overlap_with_tfidf for r in results) / total if total else 0.0, avg_hybrid_overlap_with_vector=sum(r.hybrid_overlap_with_vector for r in results) / total if total else 0.0)


def write_retrieval_mode_eval_summary(summary: RetrievalModeEvalSummary, output_path: Path) -> None:
    output_path.parent.mkdir(parents=True, exist_ok=True)
    output_path.write_text(json.dumps(asdict(summary), ensure_ascii=False, indent=2), encoding="utf-8")


def load_queries(path: Path) -> list[RetrievalComparisonQuery]:
    return load_retrieval_comparison_queries(path)
