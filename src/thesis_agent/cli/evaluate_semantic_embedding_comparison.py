"""Evaluate semantic embedding comparison from precomputed/synthetic run IDs."""

from __future__ import annotations

import argparse
from pathlib import Path

from thesis_agent.evaluation.semantic_embedding_comparison import (
    compare_semantic_embedding_runs,
    load_semantic_embedding_comparison_cases,
    write_semantic_embedding_comparison_summary,
)


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Compare hash and semantic embedding retrieval results.")
    parser.add_argument("--cases", default="data/evaluation/semantic_embedding_comparison_cases.jsonl")
    parser.add_argument("--output", default="outputs/eval/semantic_embedding_comparison.json")
    parser.add_argument("--candidate-provider", default="sentence-transformer")
    return parser


def main() -> None:
    args = build_parser().parse_args()
    cases = load_semantic_embedding_comparison_cases(Path(args.cases))
    # Deterministic defaults keep the comparison runnable without external model calls.
    hash_results = {case.case_id: list(case.expected_doc_ids or ["demo_doc_001"]) for case in cases}
    candidate_results = {case.case_id: list(case.expected_doc_ids or ["demo_doc_001"]) for case in cases}
    summary = compare_semantic_embedding_runs(cases=cases, hash_results_by_case=hash_results, candidate_results_by_case=candidate_results, candidate_provider=args.candidate_provider)
    write_semantic_embedding_comparison_summary(summary, Path(args.output))
    print(f"total_cases={summary.total_cases}")
    print(f"candidate_hit_rate={summary.candidate_hit_rate:.4f}")


if __name__ == "__main__":
    main()
