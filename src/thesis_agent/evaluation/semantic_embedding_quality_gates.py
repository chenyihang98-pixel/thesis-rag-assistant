"""Quality gates for semantic embedding comparison summaries."""

from __future__ import annotations

import json
from dataclasses import asdict, dataclass
from pathlib import Path


@dataclass
class SemanticEmbeddingQualityGateResult:
    name: str
    ok: bool
    actual: object
    expected: object


@dataclass
class SemanticEmbeddingQualityGateSummary:
    ok: bool
    total_gates: int
    passed_gates: int
    failed_gates: int
    results: list[SemanticEmbeddingQualityGateResult]


def load_semantic_embedding_quality_config(path: Path) -> dict:
    return json.loads(path.read_text(encoding="utf-8"))


def evaluate_semantic_embedding_quality_gates(summary: dict, config: dict) -> SemanticEmbeddingQualityGateSummary:
    checks = [
        ("min_total_cases", summary.get("total_cases", 0), ">=", config.get("min_total_cases")),
        ("min_candidate_hit_rate", summary.get("candidate_hit_rate", 0.0), ">=", config.get("min_candidate_hit_rate")),
        ("min_average_overlap", summary.get("average_overlap", 0.0), ">=", config.get("min_average_overlap")),
    ]
    results = []
    for name, actual, op, expected in checks:
        if expected is None:
            continue
        ok = actual >= expected if op == ">=" else actual <= expected
        results.append(SemanticEmbeddingQualityGateResult(name=name, ok=ok, actual=actual, expected=expected))
    failed = [result for result in results if not result.ok]
    return SemanticEmbeddingQualityGateSummary(ok=not failed, total_gates=len(results), passed_gates=sum(1 for result in results if result.ok), failed_gates=len(failed), results=results)


def write_semantic_embedding_quality_report(summary: SemanticEmbeddingQualityGateSummary, output_path: Path) -> None:
    output_path.parent.mkdir(parents=True, exist_ok=True)
    output_path.write_text(json.dumps(asdict(summary), ensure_ascii=False, indent=2), encoding="utf-8")
