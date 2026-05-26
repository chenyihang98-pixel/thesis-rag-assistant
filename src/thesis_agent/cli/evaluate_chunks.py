"""Evaluate fixed and structured chunk artifacts."""

from __future__ import annotations

import argparse
from pathlib import Path

from thesis_agent.evaluation.chunk_eval import ChunkEvalSummary, compare_fixed_structured_retrieval, evaluate_chunk_file, load_retrieval_comparison_queries, write_chunk_eval_summary


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Evaluate chunk quality and retrieval overlap.")
    parser.add_argument("--fixed-chunks", default="data/processed/chunks.jsonl")
    parser.add_argument("--structured-chunks", default="data/processed/structured_chunks.jsonl")
    parser.add_argument("--fixed-index", default="")
    parser.add_argument("--structured-index", default="")
    parser.add_argument("--queries", default="data/evaluation/retrieval_comparison_queries.jsonl")
    parser.add_argument("--output", default="outputs/eval/chunk_eval_summary.json")
    parser.add_argument("--fail-on-error", action="store_true")
    return parser


def main() -> None:
    args = build_parser().parse_args()
    summary = ChunkEvalSummary()
    if Path(args.fixed_chunks).exists():
        summary.fixed_eval = evaluate_chunk_file(Path(args.fixed_chunks), mode="fixed")
    if Path(args.structured_chunks).exists():
        summary.structured_eval = evaluate_chunk_file(Path(args.structured_chunks), mode="structured")
    if args.fixed_index and args.structured_index and Path(args.fixed_index).exists() and Path(args.structured_index).exists():
        summary.retrieval_comparisons = compare_fixed_structured_retrieval(Path(args.fixed_index), Path(args.structured_index), load_retrieval_comparison_queries(Path(args.queries)))
    summary.ok = all(item.ok for item in [summary.fixed_eval, summary.structured_eval] if item is not None)
    write_chunk_eval_summary(summary, Path(args.output))
    print(f"ok={summary.ok}")
    print(f"output={args.output}")
    if args.fail_on_error and not summary.ok:
        raise SystemExit(1)


if __name__ == "__main__":
    main()
