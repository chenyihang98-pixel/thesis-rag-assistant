"""Render an aggregate evaluation report."""

from __future__ import annotations

import argparse
from pathlib import Path

from thesis_agent.evaluation.reporting import build_evaluation_report, write_evaluation_report


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Render ThesisAgent evaluation reports.")
    parser.add_argument("--agent-summary", default="outputs/eval/agent_eval_results.json")
    parser.add_argument("--chunk-summary", default="outputs/eval/chunk_eval_summary.json")
    parser.add_argument("--chunk-quality-report", default="outputs/eval/quality_gate_report.json")
    parser.add_argument("--retrieval-mode-summary", default="outputs/eval/retrieval_mode_eval.json")
    parser.add_argument("--retrieval-quality-report", default="outputs/eval/retrieval_quality_report.json")
    parser.add_argument("--retrieval-relevance-summary", default="outputs/eval/retrieval_relevance_eval.json")
    parser.add_argument("--retrieval-relevance-quality-report", default="outputs/eval/retrieval_relevance_quality_report.json")
    parser.add_argument("--semantic-embedding-summary", default="outputs/eval/semantic_embedding_comparison.json")
    parser.add_argument("--semantic-embedding-quality-report", default="outputs/eval/semantic_embedding_quality_report.json")
    parser.add_argument("--multilingual-vector-smoke-summary", default="outputs/eval/multilingual_vector_smoke.json")
    parser.add_argument("--rag-answer-summary", default="outputs/eval/rag_answer_eval.json")
    parser.add_argument("--rag-answer-quality-report", default="outputs/eval/rag_answer_quality_report.json")
    parser.add_argument("--ollama-rag-answer-summary", default="outputs/eval/rag_answer_eval_ollama.json")
    parser.add_argument("--rag-answer-run-comparison", default="outputs/eval/rag_answer_run_comparison.json")
    parser.add_argument("--agent-rag-answer-summary", default="outputs/eval/agent_rag_answer_eval.json")
    parser.add_argument("--agent-rag-answer-quality-report", default="outputs/eval/agent_rag_answer_quality_report.json")
    parser.add_argument("--agent-rag-answer-run-comparison", default="outputs/eval/agent_rag_answer_run_comparison.json")
    parser.add_argument("--output", default="outputs/eval/evaluation_report.md")
    parser.add_argument("--json-output", default="")
    return parser


def _optional(path: str) -> Path | None:
    return Path(path) if path else None


def main() -> None:
    args = build_parser().parse_args()
    report = build_evaluation_report(
        agent_summary_path=_optional(args.agent_summary),
        chunk_summary_path=_optional(args.chunk_summary),
        chunk_quality_report_path=_optional(args.chunk_quality_report),
        retrieval_mode_summary_path=_optional(args.retrieval_mode_summary),
        retrieval_quality_report_path=_optional(args.retrieval_quality_report),
        retrieval_relevance_summary_path=_optional(args.retrieval_relevance_summary),
        retrieval_relevance_quality_report_path=_optional(args.retrieval_relevance_quality_report),
        semantic_embedding_summary_path=_optional(args.semantic_embedding_summary),
        semantic_embedding_quality_report_path=_optional(args.semantic_embedding_quality_report),
        multilingual_vector_smoke_summary_path=_optional(args.multilingual_vector_smoke_summary),
        rag_answer_summary_path=_optional(args.rag_answer_summary),
        rag_answer_quality_report_path=_optional(args.rag_answer_quality_report),
        ollama_rag_answer_summary_path=_optional(args.ollama_rag_answer_summary),
        rag_answer_run_comparison_path=_optional(args.rag_answer_run_comparison),
        agent_rag_answer_summary_path=_optional(args.agent_rag_answer_summary),
        agent_rag_answer_quality_report_path=_optional(args.agent_rag_answer_quality_report),
        agent_rag_answer_run_comparison_path=_optional(args.agent_rag_answer_run_comparison),
    )
    write_evaluation_report(report, Path(args.output), Path(args.json_output) if args.json_output else None)
    print(f"output={args.output}")
    if args.json_output:
        print(f"json_output={args.json_output}")
    print(f"warnings={len(report.warnings)}")


if __name__ == "__main__":
    main()
