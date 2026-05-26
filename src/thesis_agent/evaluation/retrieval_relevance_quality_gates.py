"""Quality gates for retrieval relevance summaries."""

from __future__ import annotations

from thesis_agent.evaluation.retrieval_quality_gates import (
    RetrievalQualityGateSummary,
    evaluate_retrieval_quality_gates,
    load_retrieval_quality_config,
    write_retrieval_quality_report,
)


def evaluate_retrieval_relevance_quality_gates(summary: dict, config: dict) -> RetrievalQualityGateSummary:
    adapted = {
        "total_cases": summary.get("total_cases", 0),
        "avg_hybrid_overlap_with_tfidf": summary.get("pass_rate", 0.0),
        "avg_hybrid_overlap_with_vector": summary.get("hit_rate", 0.0),
        "warnings": summary.get("warnings", []),
    }
    adapted_config = {
        "min_total_cases": config.get("min_total_cases"),
        "min_avg_hybrid_overlap_with_tfidf": config.get("min_pass_rate", config.get("min_hit_rate")),
        "min_avg_hybrid_overlap_with_vector": config.get("min_hit_rate"),
        "max_warning_cases": config.get("max_warning_cases"),
    }
    return evaluate_retrieval_quality_gates(adapted, adapted_config)


__all__ = [
    "RetrievalQualityGateSummary",
    "evaluate_retrieval_relevance_quality_gates",
    "load_retrieval_quality_config",
    "write_retrieval_quality_report",
]
