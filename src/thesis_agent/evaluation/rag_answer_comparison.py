"""Compare two RAG answer eval runs."""

from __future__ import annotations

import json
from dataclasses import asdict, dataclass, field
from pathlib import Path


@dataclass
class RagAnswerRunComparisonResult:
    case_id: str
    query: str
    baseline_ok: bool
    candidate_ok: bool
    baseline_citations: list[str]
    candidate_citations: list[str]
    citation_overlap: float
    baseline_failed_checks: list[str]
    candidate_failed_checks: list[str]
    candidate_new_warnings: list[str]
    warnings: list[str] = field(default_factory=list)


@dataclass
class RagAnswerRunComparisonSummary:
    total_cases: int
    compared_cases: int
    baseline_pass_rate: float
    candidate_pass_rate: float
    citation_overlap_avg: float
    candidate_regression_cases: list[str]
    candidate_improvement_cases: list[str]
    results: list[RagAnswerRunComparisonResult]
    warnings: list[str] = field(default_factory=list)
    metadata: dict = field(default_factory=dict)


def load_rag_answer_eval_summary(path: Path) -> dict:
    return json.loads(path.read_text(encoding="utf-8"))


def _overlap(left: list[str], right: list[str]) -> float:
    left_set, right_set = set(left), set(right)
    if not left_set and not right_set:
        return 1.0
    return len(left_set & right_set) / max(len(left_set | right_set), 1)


def compare_rag_answer_runs(baseline_summary: dict, candidate_summary: dict) -> RagAnswerRunComparisonSummary:
    baseline = {item["case_id"]: item for item in baseline_summary.get("results", [])}
    candidate = {item["case_id"]: item for item in candidate_summary.get("results", [])}
    results: list[RagAnswerRunComparisonResult] = []
    regressions: list[str] = []
    improvements: list[str] = []
    for case_id in sorted(set(baseline) & set(candidate)):
        left, right = baseline[case_id], candidate[case_id]
        overlap = _overlap(left.get("citations", []), right.get("citations", []))
        if left.get("ok") and not right.get("ok"):
            regressions.append(case_id)
        if not left.get("ok") and right.get("ok"):
            improvements.append(case_id)
        results.append(
            RagAnswerRunComparisonResult(
                case_id=case_id,
                query=left.get("query", right.get("query", "")),
                baseline_ok=bool(left.get("ok")),
                candidate_ok=bool(right.get("ok")),
                baseline_citations=left.get("citations", []),
                candidate_citations=right.get("citations", []),
                citation_overlap=overlap,
                baseline_failed_checks=left.get("failed_checks", []),
                candidate_failed_checks=right.get("failed_checks", []),
                candidate_new_warnings=[w for w in right.get("warnings", []) if w not in left.get("warnings", [])],
            )
        )
    return RagAnswerRunComparisonSummary(
        total_cases=max(baseline_summary.get("total_cases", 0), candidate_summary.get("total_cases", 0)),
        compared_cases=len(results),
        baseline_pass_rate=baseline_summary.get("pass_rate", 0.0),
        candidate_pass_rate=candidate_summary.get("pass_rate", 0.0),
        citation_overlap_avg=sum(item.citation_overlap for item in results) / len(results) if results else 0.0,
        candidate_regression_cases=regressions,
        candidate_improvement_cases=improvements,
        results=results,
    )


def write_rag_answer_run_comparison(summary: RagAnswerRunComparisonSummary, output_path: Path) -> None:
    output_path.parent.mkdir(parents=True, exist_ok=True)
    output_path.write_text(json.dumps(asdict(summary), ensure_ascii=False, indent=2), encoding="utf-8")
