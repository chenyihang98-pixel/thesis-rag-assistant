"""Evaluation for explicit Agent rag_answer task."""

from __future__ import annotations

import json
import re
from dataclasses import asdict, dataclass, field
from pathlib import Path

from thesis_agent.agent.orchestrator import AgentOrchestrator

PATH_PATTERN = re.compile(r"([A-Za-z]:\\|/home/)")


@dataclass
class AgentRagAnswerEvalCase:
    case_id: str
    query: str
    language: str = "zh"
    retrieval_mode: str = "hybrid"
    llm_provider: str = "mock"
    top_k: int = 3
    min_citation_count: int = 1
    required_terms: list[str] = field(default_factory=list)
    forbidden_terms: list[str] = field(default_factory=list)
    notes: str = ""


@dataclass
class AgentRagAnswerEvalResult:
    case_id: str
    ok: bool
    query: str
    answer_preview: str
    citations: list[str]
    citation_count: int
    retrieved_count: int
    tool_ok: bool
    intent: str
    warnings: list[str] = field(default_factory=list)
    errors: list[str] = field(default_factory=list)
    failed_checks: list[str] = field(default_factory=list)
    metadata: dict = field(default_factory=dict)


@dataclass
class AgentRagAnswerEvalSummary:
    total_cases: int
    passed_cases: int
    failed_cases: int
    pass_rate: float
    citation_rate: float
    empty_answer_cases: int
    tool_error_cases: int
    reasoning_leakage_cases: int
    absolute_path_hit_cases: int
    forbidden_term_hit_cases: int
    hallucinated_citation_cases: int
    results: list[AgentRagAnswerEvalResult]
    warnings: list[str] = field(default_factory=list)
    metadata: dict = field(default_factory=dict)


def load_agent_rag_answer_cases(path: Path) -> list[AgentRagAnswerEvalCase]:
    cases: list[AgentRagAnswerEvalCase] = []
    with path.open("r", encoding="utf-8") as handle:
        for line in handle:
            stripped = line.strip()
            if stripped:
                data = json.loads(stripped)
                cases.append(AgentRagAnswerEvalCase(**{key: data[key] for key in data if key in AgentRagAnswerEvalCase.__dataclass_fields__}))
    return cases


def evaluate_agent_rag_answer_case(case: AgentRagAnswerEvalCase, **kwargs) -> AgentRagAnswerEvalResult:
    run = AgentOrchestrator().run(
        query=case.query,
        task="rag_answer",
        index_path=kwargs.get("index_path"),
        tfidf_index_path=kwargs.get("index_path"),
        vector_persist_dir=kwargs.get("vector_persist_dir"),
        vector_collection=kwargs.get("vector_collection", "thesis_agent_demo"),
        embedding_provider_name=kwargs.get("embedding_provider", "hash"),
        llm_provider_name=kwargs.get("llm_provider") or case.llm_provider,
        retrieval_mode=kwargs.get("retrieval_mode") or case.retrieval_mode,
        top_k=int(kwargs.get("top_k") or case.top_k),
        language=kwargs.get("language") or case.language,
        ollama_base_url=kwargs.get("ollama_base_url", "http://localhost:11434"),
        ollama_model=kwargs.get("ollama_model"),
    )
    answer = run.final_answer or ""
    failed: list[str] = []
    if run.intent != "rag_answer":
        failed.append("wrong_intent")
    if not run.ok:
        failed.append("tool_error")
    if not answer.strip():
        failed.append("empty_answer")
    if len(run.citations) < case.min_citation_count:
        failed.append("missing_citation")
    forbidden = [term for term in case.forbidden_terms if term.lower() in answer.lower()]
    if forbidden:
        failed.append("forbidden_terms")
    if "<think>" in answer.lower() or "</think>" in answer.lower():
        failed.append("reasoning_leakage")
    path_hits = len(PATH_PATTERN.findall(answer))
    if path_hits:
        failed.append("absolute_path_leakage")
    return AgentRagAnswerEvalResult(
        case_id=case.case_id,
        ok=not failed,
        query=case.query,
        answer_preview=answer[:240],
        citations=run.citations,
        citation_count=len(run.citations),
        retrieved_count=int(run.metadata.get("retrieved_count", 0) or 0),
        tool_ok=run.ok,
        intent=run.intent,
        warnings=run.warnings,
        errors=run.errors,
        failed_checks=failed,
        metadata=run.metadata,
    )


def evaluate_agent_rag_answer_cases(cases: list[AgentRagAnswerEvalCase], **kwargs) -> AgentRagAnswerEvalSummary:
    results = [evaluate_agent_rag_answer_case(case, **kwargs) for case in cases]
    total = len(results)
    passed = sum(1 for result in results if result.ok)
    return AgentRagAnswerEvalSummary(
        total_cases=total,
        passed_cases=passed,
        failed_cases=total - passed,
        pass_rate=(passed / total if total else 0.0),
        citation_rate=sum(1 for result in results if result.citation_count > 0) / total if total else 0.0,
        empty_answer_cases=sum(1 for result in results if "empty_answer" in result.failed_checks),
        tool_error_cases=sum(1 for result in results if "tool_error" in result.failed_checks),
        reasoning_leakage_cases=sum(1 for result in results if "reasoning_leakage" in result.failed_checks),
        absolute_path_hit_cases=sum(1 for result in results if "absolute_path_leakage" in result.failed_checks),
        forbidden_term_hit_cases=sum(1 for result in results if "forbidden_terms" in result.failed_checks),
        hallucinated_citation_cases=0,
        results=results,
    )


def write_agent_rag_answer_eval_summary(summary: AgentRagAnswerEvalSummary, output_path: Path) -> None:
    output_path.parent.mkdir(parents=True, exist_ok=True)
    output_path.write_text(json.dumps(asdict(summary), ensure_ascii=False, indent=2), encoding="utf-8")
