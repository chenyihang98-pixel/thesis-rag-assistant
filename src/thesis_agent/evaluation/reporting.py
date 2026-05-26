"""Render lightweight evaluation reports."""

from __future__ import annotations

import json
from dataclasses import asdict, dataclass, field
from pathlib import Path


@dataclass
class EvaluationReport:
    agent_summary: dict | None = None
    chunk_summary: dict | None = None
    chunk_quality_summary: dict | None = None
    retrieval_mode_summary: dict | None = None
    retrieval_quality_summary: dict | None = None
    retrieval_relevance_summary: dict | None = None
    retrieval_relevance_quality_summary: dict | None = None
    semantic_embedding_summary: dict | None = None
    semantic_embedding_quality_summary: dict | None = None
    multilingual_vector_smoke_summary: dict | None = None
    rag_answer_summary: dict | None = None
    rag_answer_quality_summary: dict | None = None
    ollama_rag_answer_summary: dict | None = None
    rag_answer_run_comparison_summary: dict | None = None
    agent_rag_answer_summary: dict | None = None
    agent_rag_answer_quality_summary: dict | None = None
    agent_rag_answer_run_comparison_summary: dict | None = None
    warnings: list[str] = field(default_factory=list)


def _load_json_if_exists(path: Path | None, warnings: list[str]) -> dict | None:
    if path is None:
        return None
    if not path.exists():
        warnings.append(f"missing_report_input:{path.as_posix()}")
        return None
    return json.loads(path.read_text(encoding="utf-8"))


def build_evaluation_report(
    *,
    agent_summary_path: Path | None = None,
    chunk_summary_path: Path | None = None,
    chunk_quality_report_path: Path | None = None,
    retrieval_mode_summary_path: Path | None = None,
    retrieval_quality_report_path: Path | None = None,
    retrieval_relevance_summary_path: Path | None = None,
    retrieval_relevance_quality_report_path: Path | None = None,
    semantic_embedding_summary_path: Path | None = None,
    semantic_embedding_quality_report_path: Path | None = None,
    multilingual_vector_smoke_summary_path: Path | None = None,
    rag_answer_summary_path: Path | None = None,
    rag_answer_quality_report_path: Path | None = None,
    ollama_rag_answer_summary_path: Path | None = None,
    rag_answer_run_comparison_path: Path | None = None,
    agent_rag_answer_summary_path: Path | None = None,
    agent_rag_answer_quality_report_path: Path | None = None,
    agent_rag_answer_run_comparison_path: Path | None = None,
) -> EvaluationReport:
    warnings: list[str] = []
    return EvaluationReport(
        agent_summary=_load_json_if_exists(agent_summary_path, warnings),
        chunk_summary=_load_json_if_exists(chunk_summary_path, warnings),
        chunk_quality_summary=_load_json_if_exists(chunk_quality_report_path, warnings),
        retrieval_mode_summary=_load_json_if_exists(retrieval_mode_summary_path, warnings),
        retrieval_quality_summary=_load_json_if_exists(retrieval_quality_report_path, warnings),
        retrieval_relevance_summary=_load_json_if_exists(retrieval_relevance_summary_path, warnings),
        retrieval_relevance_quality_summary=_load_json_if_exists(retrieval_relevance_quality_report_path, warnings),
        semantic_embedding_summary=_load_json_if_exists(semantic_embedding_summary_path, warnings),
        semantic_embedding_quality_summary=_load_json_if_exists(semantic_embedding_quality_report_path, warnings),
        multilingual_vector_smoke_summary=_load_json_if_exists(multilingual_vector_smoke_summary_path, warnings),
        rag_answer_summary=_load_json_if_exists(rag_answer_summary_path, warnings),
        rag_answer_quality_summary=_load_json_if_exists(rag_answer_quality_report_path, warnings),
        ollama_rag_answer_summary=_load_json_if_exists(ollama_rag_answer_summary_path, warnings),
        rag_answer_run_comparison_summary=_load_json_if_exists(rag_answer_run_comparison_path, warnings),
        agent_rag_answer_summary=_load_json_if_exists(agent_rag_answer_summary_path, warnings),
        agent_rag_answer_quality_summary=_load_json_if_exists(agent_rag_answer_quality_report_path, warnings),
        agent_rag_answer_run_comparison_summary=_load_json_if_exists(agent_rag_answer_run_comparison_path, warnings),
        warnings=warnings,
    )


def _summary_lines(title: str, summary: dict | None) -> list[str]:
    if not summary:
        return [f"## {title}", "", "Not available.", ""]
    lines = [f"## {title}", ""]
    for key in ["total_cases", "passed_cases", "failed_cases", "pass_rate", "citation_rate", "ok", "passed_gates", "failed_gates", "warning_gates", "compared_cases", "citation_overlap_avg"]:
        if key in summary:
            lines.append(f"- {key}: {summary[key]}")
    lines.append("")
    return lines


def render_evaluation_report_markdown(report: EvaluationReport) -> str:
    lines = ["# ThesisAgent Evaluation Report", ""]
    lines.extend(_summary_lines("Agent Evaluation", report.agent_summary))
    lines.extend(_summary_lines("Chunk Evaluation", report.chunk_summary))
    lines.extend(_summary_lines("Chunk Quality Gates", report.chunk_quality_summary))
    lines.extend(_summary_lines("Retrieval Mode Evaluation", report.retrieval_mode_summary))
    lines.extend(_summary_lines("Retrieval Quality Gates", report.retrieval_quality_summary))
    lines.extend(_summary_lines("Retrieval Relevance Evaluation", report.retrieval_relevance_summary))
    lines.extend(_summary_lines("Retrieval Relevance Quality Gates", report.retrieval_relevance_quality_summary))
    lines.extend(_summary_lines("Semantic Embedding Comparison", report.semantic_embedding_summary))
    lines.extend(_summary_lines("Semantic Embedding Quality Gates", report.semantic_embedding_quality_summary))
    lines.extend(_summary_lines("Multilingual Vector Smoke", report.multilingual_vector_smoke_summary))
    lines.extend(_summary_lines("RAG Answer Evaluation", report.rag_answer_summary))
    lines.extend(_summary_lines("RAG Answer Quality Gates", report.rag_answer_quality_summary))
    lines.extend(_summary_lines("Ollama RAG Answer Evaluation", report.ollama_rag_answer_summary))
    lines.extend(_summary_lines("Mock vs Ollama RAG Answer Comparison", report.rag_answer_run_comparison_summary))
    lines.extend(_summary_lines("Agent RAG Answer Evaluation", report.agent_rag_answer_summary))
    lines.extend(_summary_lines("Agent RAG Answer Quality Gates", report.agent_rag_answer_quality_summary))
    lines.extend(_summary_lines("Agent RAG Answer Mock vs Ollama Comparison", report.agent_rag_answer_run_comparison_summary))
    if report.warnings:
        lines.extend(["## Warnings", ""])
        lines.extend([f"- {warning}" for warning in report.warnings])
    return "\n".join(lines).rstrip() + "\n"


def write_evaluation_report(report: EvaluationReport, markdown_path: Path, json_path: Path | None = None) -> None:
    markdown_path.parent.mkdir(parents=True, exist_ok=True)
    markdown_path.write_text(render_evaluation_report_markdown(report), encoding="utf-8")
    if json_path:
        json_path.parent.mkdir(parents=True, exist_ok=True)
        json_path.write_text(json.dumps(asdict(report), ensure_ascii=False, indent=2), encoding="utf-8")


def compare_evaluation_reports(left: EvaluationReport, right: EvaluationReport) -> dict:
    return {
        "left_warnings": left.warnings,
        "right_warnings": right.warnings,
        "rag_pass_rate_delta": _get(right.rag_answer_summary, "pass_rate") - _get(left.rag_answer_summary, "pass_rate"),
        "agent_rag_pass_rate_delta": _get(right.agent_rag_answer_summary, "pass_rate") - _get(left.agent_rag_answer_summary, "pass_rate"),
    }


def _get(summary: dict | None, key: str) -> float:
    if not summary:
        return 0.0
    return float(summary.get(key, 0.0) or 0.0)
