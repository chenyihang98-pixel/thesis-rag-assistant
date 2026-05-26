"""Chunk quality evaluation helpers."""

from __future__ import annotations

import json
from dataclasses import asdict, dataclass, field
from pathlib import Path

from thesis_agent.pipeline.retrieval import search_tfidf_index
from thesis_agent.retrieval.io import load_chunks_jsonl


@dataclass
class ChunkEvalResult:
    ok: bool
    chunk_count: int
    document_count: int
    section_types: dict[str, int]
    section_coverage: dict[str, bool]
    metadata_completeness: dict[str, float]
    high_value_section_count: int
    low_priority_section_count: int
    high_value_ratio: float
    low_priority_ratio: float
    warnings: list[str] = field(default_factory=list)
    errors: list[str] = field(default_factory=list)
    metadata: dict = field(default_factory=dict)


@dataclass
class RetrievalComparisonQuery:
    query: str
    expected_terms: list[str] = field(default_factory=list)
    language: str = "ja"
    top_k: int = 3


@dataclass
class RetrievalComparisonResult:
    query: str
    fixed_top_doc_ids: list[str]
    structured_top_doc_ids: list[str]
    overlap_count: int
    overlap_ratio: float
    fixed_result_count: int
    structured_result_count: int
    warnings: list[str] = field(default_factory=list)
    metadata: dict = field(default_factory=dict)


@dataclass
class ChunkEvalSummary:
    fixed_eval: ChunkEvalResult | None = None
    structured_eval: ChunkEvalResult | None = None
    retrieval_comparisons: list[RetrievalComparisonResult] = field(default_factory=list)
    ok: bool = True
    warnings: list[str] = field(default_factory=list)
    errors: list[str] = field(default_factory=list)


def evaluate_chunk_file(path: Path, mode: str = "structured") -> ChunkEvalResult:
    chunks = load_chunks_jsonl(path)
    section_types: dict[str, int] = {}
    fields = ["embedding_text", "display_text", "section_type", "heading_path", "chunk_index", "doc_id", "chunk_id", "title", "text"]
    present_counts = {field: 0 for field in fields}
    for chunk in chunks:
        metadata = chunk.get("metadata", {})
        section_type = chunk.get("section_type") or metadata.get("section_type") or "body"
        section_types[section_type] = section_types.get(section_type, 0) + 1
        for field_name in fields:
            if chunk.get(field_name) not in (None, "", []):
                present_counts[field_name] += 1
            elif metadata.get(field_name) not in (None, "", []):
                present_counts[field_name] += 1
    total = len(chunks) or 1
    completeness = {field: present_counts[field] / total for field in fields}
    high = sum(count for kind, count in section_types.items() if kind in {"abstract", "method", "experiment", "result", "conclusion"})
    low = sum(count for kind, count in section_types.items() if kind in {"references", "acknowledgement"})
    coverage = {kind: kind in section_types for kind in ["abstract", "method", "experiment", "result", "conclusion", "body"]}
    warnings: list[str] = []
    if mode == "structured" and completeness["embedding_text"] < 1.0:
        warnings.append("missing_embedding_text")
    if not any(coverage[kind] for kind in ["abstract", "method", "experiment", "result", "conclusion"]):
        warnings.append("no_high_value_sections")
    return ChunkEvalResult(
        ok=not warnings or mode == "fixed",
        chunk_count=len(chunks),
        document_count=len({chunk.get("doc_id") for chunk in chunks}),
        section_types=section_types,
        section_coverage=coverage,
        metadata_completeness=completeness,
        high_value_section_count=high,
        low_priority_section_count=low,
        high_value_ratio=high / total,
        low_priority_ratio=low / total,
        warnings=warnings,
        metadata={"mode": mode, "path": path.as_posix()},
    )


def load_retrieval_comparison_queries(path: Path) -> list[RetrievalComparisonQuery]:
    queries: list[RetrievalComparisonQuery] = []
    if not path.exists():
        return queries
    with path.open("r", encoding="utf-8") as handle:
        for line in handle:
            stripped = line.strip()
            if stripped:
                data = json.loads(stripped)
                queries.append(RetrievalComparisonQuery(**{key: data[key] for key in data if key in RetrievalComparisonQuery.__dataclass_fields__}))
    return queries


def compare_fixed_structured_retrieval(fixed_index_path: Path, structured_index_path: Path, queries: list[RetrievalComparisonQuery]) -> list[RetrievalComparisonResult]:
    results: list[RetrievalComparisonResult] = []
    for query in queries:
        fixed = search_tfidf_index(fixed_index_path, query.query, top_k=query.top_k)
        structured = search_tfidf_index(structured_index_path, query.query, top_k=query.top_k)
        fixed_ids = [item.doc_id for item in fixed]
        structured_ids = [item.doc_id for item in structured]
        overlap = len(set(fixed_ids) & set(structured_ids))
        results.append(
            RetrievalComparisonResult(
                query=query.query,
                fixed_top_doc_ids=fixed_ids,
                structured_top_doc_ids=structured_ids,
                overlap_count=overlap,
                overlap_ratio=overlap / max(len(set(fixed_ids) | set(structured_ids)), 1),
                fixed_result_count=len(fixed),
                structured_result_count=len(structured),
            )
        )
    return results


def write_chunk_eval_summary(summary: ChunkEvalSummary, output_path: Path) -> None:
    output_path.parent.mkdir(parents=True, exist_ok=True)
    output_path.write_text(json.dumps(asdict(summary), ensure_ascii=False, indent=2), encoding="utf-8")
