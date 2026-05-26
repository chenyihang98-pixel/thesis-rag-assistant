"""Evaluate structured chunk quality gates."""

from __future__ import annotations

import argparse
from pathlib import Path

from thesis_agent.evaluation.chunk_eval import ChunkEvalSummary, compare_fixed_structured_retrieval, evaluate_chunk_file, load_retrieval_comparison_queries
from thesis_agent.evaluation.quality_gates import evaluate_chunk_quality_gates, load_quality_gate_config, write_quality_gate_report


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Evaluate chunk quality gates.")
    parser.add_argument("--fixed-chunks", default="data/processed/chunks.jsonl")
    parser.add_argument("--structured-chunks", default="data/processed/structured_chunks.jsonl")
    parser.add_argument("--fixed-index", default="data/index/tfidf_index.pkl")
    parser.add_argument("--structured-index", default="data/index/structured_tfidf_index.pkl")
    parser.add_argument("--queries", default="data/evaluation/retrieval_comparison_queries.jsonl")
    parser.add_argument("--config", default="data/evaluation/chunk_quality_gates.json")
    parser.add_argument("--output", default="outputs/eval/quality_gate_report.json")
    parser.add_argument("--fail-on-error", action="store_true")
    return parser


def main() -> None:
    args = build_parser().parse_args()
    summary = ChunkEvalSummary(
        fixed_eval=evaluate_chunk_file(Path(args.fixed_chunks), mode="fixed"),
        structured_eval=evaluate_chunk_file(Path(args.structured_chunks), mode="structured"),
        retrieval_comparisons=compare_fixed_structured_retrieval(Path(args.fixed_index), Path(args.structured_index), load_retrieval_comparison_queries(Path(args.queries))),
    )
    gate_summary = evaluate_chunk_quality_gates(summary, load_quality_gate_config(Path(args.config)))
    write_quality_gate_report(gate_summary, Path(args.output))
    print(f"ok={gate_summary.ok}")
    print(f"passed_gates={gate_summary.passed_gates}")
    print(f"failed_gates={gate_summary.failed_gates}")
    if args.fail_on_error and not gate_summary.ok:
        raise SystemExit(1)


if __name__ == "__main__":
    main()
