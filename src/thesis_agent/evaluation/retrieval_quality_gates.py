"""Quality gates for retrieval mode evaluation."""

from __future__ import annotations

import json
from dataclasses import asdict, dataclass, field
from pathlib import Path


@dataclass
class RetrievalQualityGateResult:
    name: str
    ok: bool
    actual: object
    expected: object
    severity: str = "error"


@dataclass
class RetrievalQualityGateSummary:
    ok: bool
    total_gates: int
    passed_gates: int
    failed_gates: int
    warning_gates: int
    results: list[RetrievalQualityGateResult]
    metadata: dict = field(default_factory=dict)


def load_retrieval_quality_config(path: Path) -> dict:
    return json.loads(path.read_text(encoding="utf-8"))


def evaluate_retrieval_quality_gates(summary: dict, config: dict) -> RetrievalQualityGateSummary:
    results: list[RetrievalQualityGateResult] = []
    checks = [
        ("min_total_cases", summary.get("total_cases", 0), ">=", config.get("min_total_cases")),
        ("min_avg_hybrid_overlap_with_tfidf", summary.get("avg_hybrid_overlap_with_tfidf", 0.0), ">=", config.get("min_avg_hybrid_overlap_with_tfidf")),
        ("min_avg_hybrid_overlap_with_vector", summary.get("avg_hybrid_overlap_with_vector", 0.0), ">=", config.get("min_avg_hybrid_overlap_with_vector")),
        ("max_warning_cases", len(summary.get("warnings", []) or []), "<=", config.get("max_warning_cases")),
    ]
    for name, actual, op, expected in checks:
        if expected is None:
            continue
        ok = actual >= expected if op == ">=" else actual <= expected
        results.append(RetrievalQualityGateResult(name=name, ok=ok, actual=actual, expected=expected))
    failed = [result for result in results if not result.ok and result.severity == "error"]
    warnings = [result for result in results if not result.ok and result.severity == "warning"]
    return RetrievalQualityGateSummary(
        ok=not failed,
        total_gates=len(results),
        passed_gates=sum(1 for result in results if result.ok),
        failed_gates=len(failed),
        warning_gates=len(warnings),
        results=results,
    )


def write_retrieval_quality_report(summary: RetrievalQualityGateSummary, output_path: Path) -> None:
    output_path.parent.mkdir(parents=True, exist_ok=True)
    output_path.write_text(json.dumps(asdict(summary), ensure_ascii=False, indent=2), encoding="utf-8")
