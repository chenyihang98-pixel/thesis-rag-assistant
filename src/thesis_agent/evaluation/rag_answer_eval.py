"""RAG answer evaluation for synthetic cases."""

from __future__ import annotations

import json
import re
from dataclasses import asdict, dataclass, field
from pathlib import Path

from thesis_agent.pipeline.rag_answer import RagAnswerResult, generate_rag_answer

PATH_PATTERN = re.compile(r"([A-Za-z]:\\|/home/)")


@dataclass
class RagAnswerEvalCase:
    case_id: str
    query: str
    language: str = "zh"
    retrieval_mode: str = "hybrid"
    llm_provider: str = "mock"
    top_k: int = 3
    required_citations: list[str] = field(default_factory=list)
    required_terms: list[str] = field(default_factory=list)
    forbidden_terms: list[str] = field(default_factory=list)
    min_citation_count: int = 1
    notes: str = ""


@dataclass
class RagAnswerEvalResult:
    case_id: str
    ok: bool
    query: str
    answer_preview: str
    citations: list[str]
    retrieved_citations: list[str]
    citation_count: int
    missing_required_citations: list[str]
    hallucinated_citations: list[str]
    matched_required_terms: list[str]
    missing_required_terms: list[str]
    forbidden_term_hits: list[str]
    reasoning_leakage: bool
    absolute_path_hits: int
    warnings: list[str] = field(default_factory=list)
    failed_checks: list[str] = field(default_factory=list)
    metadata: dict = field(default_factory=dict)


@dataclass
class RagAnswerEvalSummary:
    total_cases: int
    passed_cases: int
    failed_cases: int
    pass_rate: float
    citation_rate: float
    reasoning_leakage_cases: int
    forbidden_term_hit_cases: int
    absolute_path_hit_cases: int
    hallucinated_citation_cases: int
    results: list[RagAnswerEvalResult]
    warnings: list[str] = field(default_factory=list)
    metadata: dict = field(default_factory=dict)


def load_rag_answer_cases(path: Path) -> list[RagAnswerEvalCase]:
    cases: list[RagAnswerEvalCase] = []
    with path.open("r", encoding="utf-8") as handle:
        for line in handle:
            stripped = line.strip()
            if stripped:
                data = json.loads(stripped)
                cases.append(RagAnswerEvalCase(**{key: data[key] for key in data if key in RagAnswerEvalCase.__dataclass_fields__}))
    return cases


def evaluate_rag_answer_case(case: RagAnswerEvalCase, **kwargs) -> RagAnswerEvalResult:
    result: RagAnswerResult = generate_rag_answer(
        query=case.query,
        retrieval_mode=kwargs.get("retrieval_mode") or case.retrieval_mode,
        llm_provider_name=kwargs.get("llm_provider") or case.llm_provider,
        language=kwargs.get("language") or case.language,
        top_k=int(kwargs.get("top_k") or case.top_k),
        tfidf_index_path=kwargs.get("tfidf_index_path"),
        vector_persist_dir=kwargs.get("vector_persist_dir"),
        vector_collection=kwargs.get("vector_collection", "thesis_agent_demo"),
        embedding_provider_name=kwargs.get("embedding_provider", "hash"),
        ollama_base_url=kwargs.get("ollama_base_url", "http://localhost:11434"),
        ollama_model=kwargs.get("ollama_model"),
    )
    answer = result.answer_markdown or ""
    retrieved = list(result.metadata.get("retrieved_citations", [])) or list(result.citations)
    missing_required_citations = [citation for citation in case.required_citations if citation not in result.citations]
    hallucinated = [citation for citation in result.citations if retrieved and citation not in retrieved]
    matched_terms = [term for term in case.required_terms if term in answer]
    missing_terms = [term for term in case.required_terms if term not in answer]
    forbidden_hits = [term for term in case.forbidden_terms if term.lower() in answer.lower()]
    reasoning = "<think>" in answer.lower() or "</think>" in answer.lower()
    path_hits = len(PATH_PATTERN.findall(answer))
    failed: list[str] = []
    if not result.ok:
        failed.append("generation_failed")
    if len(result.citations) < case.min_citation_count:
        failed.append("missing_citation")
    if missing_required_citations:
        failed.append("missing_required_citation")
    if hallucinated:
        failed.append("hallucinated_citation")
    if missing_terms:
        failed.append("missing_required_terms")
    if forbidden_hits:
        failed.append("forbidden_terms")
    if reasoning:
        failed.append("reasoning_leakage")
    if path_hits:
        failed.append("absolute_path_leakage")
    return RagAnswerEvalResult(
        case_id=case.case_id,
        ok=not failed,
        query=case.query,
        answer_preview=answer[:240],
        citations=result.citations,
        retrieved_citations=retrieved,
        citation_count=len(result.citations),
        missing_required_citations=missing_required_citations,
        hallucinated_citations=hallucinated,
        matched_required_terms=matched_terms,
        missing_required_terms=missing_terms,
        forbidden_term_hits=forbidden_hits,
        reasoning_leakage=reasoning,
        absolute_path_hits=path_hits,
        warnings=result.warnings,
        failed_checks=failed,
        metadata=result.metadata,
    )


def evaluate_rag_answer_cases(cases: list[RagAnswerEvalCase], **kwargs) -> RagAnswerEvalSummary:
    results = [evaluate_rag_answer_case(case, **kwargs) for case in cases]
    total = len(results)
    passed = sum(1 for result in results if result.ok)
    citation_cases = sum(1 for result in results if result.citation_count > 0)
    return RagAnswerEvalSummary(
        total_cases=total,
        passed_cases=passed,
        failed_cases=total - passed,
        pass_rate=(passed / total if total else 0.0),
        citation_rate=(citation_cases / total if total else 0.0),
        reasoning_leakage_cases=sum(1 for result in results if result.reasoning_leakage),
        forbidden_term_hit_cases=sum(1 for result in results if result.forbidden_term_hits),
        absolute_path_hit_cases=sum(1 for result in results if result.absolute_path_hits),
        hallucinated_citation_cases=sum(1 for result in results if result.hallucinated_citations),
        results=results,
    )


def write_rag_answer_eval_summary(summary: RagAnswerEvalSummary, output_path: Path) -> None:
    output_path.parent.mkdir(parents=True, exist_ok=True)
    output_path.write_text(json.dumps(asdict(summary), ensure_ascii=False, indent=2), encoding="utf-8")
