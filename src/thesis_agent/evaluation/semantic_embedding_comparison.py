"""Hash vs sentence-transformer retrieval comparison helpers."""

from __future__ import annotations

import json
from dataclasses import asdict, dataclass, field
from pathlib import Path


@dataclass
class SemanticEmbeddingComparisonCase:
    case_id: str
    query: str
    expected_doc_ids: list[str] = field(default_factory=list)
    top_k: int = 3
    language: str = "ja"


@dataclass
class SemanticEmbeddingComparisonResult:
    case_id: str
    query: str
    hash_doc_ids: list[str]
    candidate_doc_ids: list[str]
    overlap: float
    candidate_hit: bool
    warnings: list[str] = field(default_factory=list)


@dataclass
class SemanticEmbeddingComparisonSummary:
    total_cases: int
    candidate_hit_rate: float
    average_overlap: float
    results: list[SemanticEmbeddingComparisonResult]
    warnings: list[str] = field(default_factory=list)
    metadata: dict = field(default_factory=dict)


def load_semantic_embedding_comparison_cases(path: Path) -> list[SemanticEmbeddingComparisonCase]:
    cases: list[SemanticEmbeddingComparisonCase] = []
    if not path.exists():
        return cases
    with path.open("r", encoding="utf-8") as handle:
        for line in handle:
            if line.strip():
                data = json.loads(line)
                allowed = {key: data[key] for key in data if key in SemanticEmbeddingComparisonCase.__dataclass_fields__}
                cases.append(SemanticEmbeddingComparisonCase(**allowed))
    return cases


def compare_semantic_embedding_runs(
    *,
    cases: list[SemanticEmbeddingComparisonCase],
    hash_results_by_case: dict[str, list[str]],
    candidate_results_by_case: dict[str, list[str]],
    candidate_provider: str = "sentence-transformer",
) -> SemanticEmbeddingComparisonSummary:
    results: list[SemanticEmbeddingComparisonResult] = []
    for case in cases:
        hash_ids = list(hash_results_by_case.get(case.case_id, []))
        candidate_ids = list(candidate_results_by_case.get(case.case_id, []))
        union = set(hash_ids) | set(candidate_ids)
        overlap = len(set(hash_ids) & set(candidate_ids)) / max(len(union), 1)
        candidate_hit = not case.expected_doc_ids or bool(set(candidate_ids) & set(case.expected_doc_ids))
        results.append(
            SemanticEmbeddingComparisonResult(
                case_id=case.case_id,
                query=case.query,
                hash_doc_ids=hash_ids,
                candidate_doc_ids=candidate_ids,
                overlap=overlap,
                candidate_hit=candidate_hit,
            )
        )
    total = len(results)
    return SemanticEmbeddingComparisonSummary(
        total_cases=total,
        candidate_hit_rate=sum(1 for result in results if result.candidate_hit) / total if total else 0.0,
        average_overlap=sum(result.overlap for result in results) / total if total else 0.0,
        results=results,
        metadata={"candidate_provider": candidate_provider},
    )


def write_semantic_embedding_comparison_summary(summary: SemanticEmbeddingComparisonSummary, output_path: Path) -> None:
    output_path.parent.mkdir(parents=True, exist_ok=True)
    output_path.write_text(json.dumps(asdict(summary), ensure_ascii=False, indent=2), encoding="utf-8")
