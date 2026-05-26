"""Evaluate retrieval mode behavior."""

from __future__ import annotations

import argparse
from pathlib import Path

from thesis_agent.evaluation.retrieval_mode_eval import evaluate_retrieval_modes, load_queries, write_retrieval_mode_eval_summary


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Evaluate TF-IDF, vector, and hybrid retrieval modes.")
    parser.add_argument("--queries", default="data/evaluation/retrieval_comparison_queries.jsonl")
    parser.add_argument("--tfidf-index", default="data/index/structured_tfidf_index.pkl")
    parser.add_argument("--vector-persist-dir", default="data/vector/chroma")
    parser.add_argument("--vector-collection", default="thesis_agent_demo")
    parser.add_argument("--embedding-provider", default="hash")
    parser.add_argument("--output", default="outputs/eval/retrieval_mode_eval.json")
    return parser


def main() -> None:
    args = build_parser().parse_args()
    summary = evaluate_retrieval_modes(
        queries=load_queries(Path(args.queries)),
        tfidf_index_path=Path(args.tfidf_index),
        vector_persist_dir=Path(args.vector_persist_dir),
        vector_collection=args.vector_collection,
        embedding_provider=args.embedding_provider,
    )
    write_retrieval_mode_eval_summary(summary, Path(args.output))
    print(f"total_cases={summary.total_cases}")
    print(f"avg_hybrid_overlap_with_tfidf={summary.avg_hybrid_overlap_with_tfidf:.4f}")
    print(f"output={args.output}")


if __name__ == "__main__":
    main()
