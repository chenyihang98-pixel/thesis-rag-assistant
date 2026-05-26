"""Quality gates for structured chunk evaluation summaries."""

from __future__ import annotations

import json
from dataclasses import asdict, dataclass, field
from pathlib import Path

from thesis_agent.evaluation.chunk_eval import ChunkEvalSummary


@dataclass
class QualityGateResult:
    name: str
    ok: bool
    actual: object
    expected: object
    message: str = ""


@dataclass
class QualityGateSummary:
    ok: bool
    total_gates: int
    passed_gates: int
    failed_gates: int
    results: list[QualityGateResult]
    metadata: dict = field(default_factory=dict)


def load_quality_gate_config(path: Path) -> dict:
    return json.loads(path.read_text(encoding="utf-8"))


def _get_eval_dict(summary: ChunkEvalSummary | dict, key: str) -> dict:
    if isinstance(summary, dict):
        return summary.get(key) or {}
    value = getattr(summary, key, None)
    return value.__dict__ if hasattr(value, "__dict__") else (value or {})


def evaluate_chunk_quality_gates(summary: ChunkEvalSummary | dict, config: dict) -> QualityGateSummary:
    structured = _get_eval_dict(summary, "structured_eval")
    fixed = _get_eval_dict(summary, "fixed_eval")
    results: list[QualityGateResult] = []

    checks = [
        ("min_structured_chunk_count", structured.get("chunk_count", 0), ">=", config.get("min_structured_chunk_count", config.get("min_chunk_count"))),
        ("min_document_count", structured.get("document_count", 0) or fixed.get("document_count", 0), ">=", config.get("min_document_count")),
        ("min_high_value_ratio", structured.get("high_value_ratio", 0.0), ">=", config.get("min_high_value_ratio")),
        ("max_low_priority_ratio", structured.get("low_priority_ratio", 0.0), "<=", config.get("max_low_priority_ratio")),
    ]
    completeness = structured.get("metadata_completeness", {}) or {}
    for field_name, threshold in (config.get("min_metadata_completeness", {}) or {}).items():
        checks.append((f"metadata_{field_name}", completeness.get(field_name, 0.0), ">=", threshold))

    for name, actual, op, expected in checks:
        if expected is None:
            continue
        ok = actual >= expected if op == ">=" else actual <= expected
        results.append(QualityGateResult(name=name, ok=ok, actual=actual, expected=expected))

    failed = [result for result in results if not result.ok]
    return QualityGateSummary(
        ok=not failed,
        total_gates=len(results),
        passed_gates=sum(1 for result in results if result.ok),
        failed_gates=len(failed),
        results=results,
    )


def write_quality_gate_report(summary: QualityGateSummary, output_path: Path) -> None:
    output_path.parent.mkdir(parents=True, exist_ok=True)
    output_path.write_text(json.dumps(asdict(summary), ensure_ascii=False, indent=2), encoding="utf-8")
