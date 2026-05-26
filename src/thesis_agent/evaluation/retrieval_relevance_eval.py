"""Query-level retrieval relevance evaluation."""

from __future__ import annotations

import json
from dataclasses import asdict, dataclass, field
from pathlib import Path

from thesis_agent.pipeline.retrieval import search_hybrid_index, search_tfidf_index, search_vector_index


@dataclass
class RetrievalRelevanceCase:
    case_id: str
    query: str
    expected_doc_ids: list[str] = field(default_factory=list)
    required_terms: list[str] = field(default_factory=list)
    language: str = "ja"
    top_k: int = 3


@dataclass
class RetrievalRelevanceResult:
    case_id: str
    query: str
    ok: bool
    retrieved_doc_ids: list[str]
    expected_doc_ids: list[str]
    hit: bool
    required_terms_found: list[str]
    failed_checks: list[str] = field(default_factory=list)


@dataclass
class RetrievalRelevanceSummary:
    total_cases: int
    passed_cases: int
    failed_cases: int
    pass_rate: float
    hit_rate: float
    results: list[RetrievalRelevanceResult]
    warnings: list[str] = field(default_factory=list)


def load_retrieval_relevance_cases(path: Path) -> list[RetrievalRelevanceCase]:
    cases: list[RetrievalRelevanceCase] = []
    if not path.exists():
        return cases
    with path.open("r", encoding="utf-8") as handle:
        for line in handle:
            if line.strip():
                data = json.loads(line)
                allowed = {key: data[key] for key in data if key in RetrievalRelevanceCase.__dataclass_fields__}
                cases.append(RetrievalRelevanceCase(**allowed))
    return cases


def evaluate_retrieval_relevance_cases(
    *,
    cases: list[RetrievalRelevanceCase],
    retrieval_mode: str,
    tfidf_index_path: Path,
    vector_persist_dir: Path | None = None,
    vector_collection: str = "thesis_agent_demo",
    embedding_provider: str = "hash",
) -> RetrievalRelevanceSummary:
    results: list[RetrievalRelevanceResult] = []
    warnings: list[str] = []
    for case in cases:
        if retrieval_mode == "vector":
            if vector_persist_dir is None:
                warnings.append("vector_index_missing")
                hits = []
            else:
                hits = search_vector_index(vector_persist_dir, case.query, top_k=case.top_k, collection_name=vector_collection, embedding_provider_name=embedding_provider)
        elif retrieval_mode == "hybrid":
            if vector_persist_dir is None:
                warnings.append("vector_index_missing_fallback_to_tfidf")
                hits = search_tfidf_index(tfidf_index_path, case.query, top_k=case.top_k)
            else:
                hits = search_hybrid_index(tfidf_index_path=tfidf_index_path, vector_persist_dir=vector_persist_dir, query=case.query, top_k=case.top_k, vector_collection=vector_collection, embedding_provider_name=embedding_provider)
        else:
            hits = search_tfidf_index(tfidf_index_path, case.query, top_k=case.top_k)
        doc_ids = [hit.doc_id for hit in hits]
        body = "\n".join(hit.title + "\n" + hit.text for hit in hits)
        expected_hit = not case.expected_doc_ids or bool(set(doc_ids) & set(case.expected_doc_ids))
        terms_found = [term for term in case.required_terms if term.lower() in body.lower()]
        failed: list[str] = []
        if not expected_hit:
            failed.append("expected_doc_not_retrieved")
        if len(terms_found) < len(case.required_terms):
            failed.append("required_terms_missing")
        results.append(
            RetrievalRelevanceResult(
                case_id=case.case_id,
                query=case.query,
                ok=not failed,
                retrieved_doc_ids=doc_ids,
                expected_doc_ids=case.expected_doc_ids,
                hit=expected_hit,
                required_terms_found=terms_found,
                failed_checks=failed,
            )
        )
    total = len(results)
    passed = sum(1 for result in results if result.ok)
    hits = sum(1 for result in results if result.hit)
    return RetrievalRelevanceSummary(total_cases=total, passed_cases=passed, failed_cases=total - passed, pass_rate=passed / total if total else 0.0, hit_rate=hits / total if total else 0.0, results=results, warnings=warnings)


def write_retrieval_relevance_summary(summary: RetrievalRelevanceSummary, output_path: Path) -> None:
    output_path.parent.mkdir(parents=True, exist_ok=True)
    output_path.write_text(json.dumps(asdict(summary), ensure_ascii=False, indent=2), encoding="utf-8")
