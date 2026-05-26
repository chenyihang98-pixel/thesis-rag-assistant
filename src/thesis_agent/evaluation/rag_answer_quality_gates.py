"""Quality gates for RAG answer eval summaries."""

from __future__ import annotations

import json
from dataclasses import asdict, dataclass, field
from pathlib import Path


@dataclass
class RagAnswerQualityGateResult:
    name: str
    ok: bool
    actual: object | None = None
    expected: object | None = None
    message: str = ""
    severity: str = "error"


@dataclass
class RagAnswerQualityGateSummary:
    ok: bool
    total_gates: int
    passed_gates: int
    failed_gates: int
    warning_gates: int
    results: list[RagAnswerQualityGateResult]
    metadata: dict = field(default_factory=dict)


def load_rag_answer_quality_config(path: Path) -> dict:
    return json.loads(path.read_text(encoding="utf-8"))


def summarize_rag_answer_eval(summary: dict | object) -> dict:
    if hasattr(summary, "__dict__"):
        summary = summary.__dict__
    return dict(summary)


def _gate(name: str, actual, expected, ok: bool, severity: str = "error") -> RagAnswerQualityGateResult:
    return RagAnswerQualityGateResult(name=name, ok=ok, actual=actual, expected=expected, severity=severity)


def evaluate_rag_answer_quality_gates(rag_summary: dict, config: dict) -> RagAnswerQualityGateSummary:
    results: list[RagAnswerQualityGateResult] = []
    checks = [
        ("min_total_cases", rag_summary.get("total_cases", 0), ">=", config.get("min_total_cases")),
        ("min_pass_rate", rag_summary.get("pass_rate", 0.0), ">=", config.get("min_pass_rate")),
        ("max_failed_cases", rag_summary.get("failed_cases", 0), "<=", config.get("max_failed_cases")),
        ("min_citation_rate", rag_summary.get("citation_rate", 0.0), ">=", config.get("min_citation_rate")),
        ("max_reasoning_leakage_cases", rag_summary.get("reasoning_leakage_cases", 0), "<=", config.get("max_reasoning_leakage_cases")),
        ("max_absolute_path_hits", rag_summary.get("absolute_path_hit_cases", rag_summary.get("absolute_path_hits", 0)), "<=", config.get("max_absolute_path_hits")),
        ("max_forbidden_term_hits", rag_summary.get("forbidden_term_hit_cases", rag_summary.get("forbidden_term_hits", 0)), "<=", config.get("max_forbidden_term_hits")),
        ("max_hallucinated_citation_cases", rag_summary.get("hallucinated_citation_cases", 0), "<=", config.get("max_hallucinated_citation_cases")),
    ]
    for name, actual, op, expected in checks:
        if expected is None:
            continue
        ok = actual >= expected if op == ">=" else actual <= expected
        results.append(_gate(name, actual, expected, ok))
    treat_advisory_as_failure = bool(config.get("treat_advisory_as_failure", False))
    advisory_checks = [
        ("max_appendix_only_rate_advisory", rag_summary.get("appendix_only_rate", 0.0), "<=", config.get("max_appendix_only_rate_advisory")),
        ("max_retry_rate_advisory", rag_summary.get("retry_rate", 0.0), "<=", config.get("max_retry_rate_advisory")),
        ("min_language_match_rate_advisory", rag_summary.get("language_match_rate", 1.0), ">=", config.get("min_language_match_rate_advisory")),
    ]
    for name, actual, op, expected in advisory_checks:
        if expected is None:
            continue
        ok = actual >= expected if op == ">=" else actual <= expected
        severity = "error" if treat_advisory_as_failure else "warning"
        results.append(_gate(name, actual, expected, ok, severity=severity))
    failed = [result for result in results if not result.ok and result.severity == "error"]
    warnings = [result for result in results if not result.ok and result.severity == "warning"]
    passed = sum(1 for result in results if result.ok)
    return RagAnswerQualityGateSummary(ok=not failed, total_gates=len(results), passed_gates=passed, failed_gates=len(failed), warning_gates=len(warnings), results=results)


def write_rag_answer_quality_report(summary: RagAnswerQualityGateSummary, output_path: Path) -> None:
    output_path.parent.mkdir(parents=True, exist_ok=True)
    output_path.write_text(json.dumps(asdict(summary), ensure_ascii=False, indent=2), encoding="utf-8")
