"""Evaluate query-level retrieval relevance."""

from __future__ import annotations

import argparse
from pathlib import Path

from thesis_agent.evaluation.retrieval_relevance_eval import evaluate_retrieval_relevance_cases, load_retrieval_relevance_cases, write_retrieval_relevance_summary


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Evaluate retrieval relevance.")
    parser.add_argument("--cases", default="data/evaluation/retrieval_relevance_cases.jsonl")
    parser.add_argument("--retrieval-mode", choices=["tfidf", "vector", "hybrid"], default="hybrid")
    parser.add_argument("--tfidf-index", default="data/index/structured_tfidf_index.pkl")
    parser.add_argument("--vector-persist-dir", default="data/vector/chroma")
    parser.add_argument("--vector-collection", default="thesis_agent_demo")
    parser.add_argument("--embedding-provider", default="hash")
    parser.add_argument("--output", default="outputs/eval/retrieval_relevance_eval.json")
    parser.add_argument("--fail-on-error", action="store_true")
    return parser


def main() -> None:
    args = build_parser().parse_args()
    summary = evaluate_retrieval_relevance_cases(
        cases=load_retrieval_relevance_cases(Path(args.cases)),
        retrieval_mode=args.retrieval_mode,
        tfidf_index_path=Path(args.tfidf_index),
        vector_persist_dir=Path(args.vector_persist_dir),
        vector_collection=args.vector_collection,
        embedding_provider=args.embedding_provider,
    )
    write_retrieval_relevance_summary(summary, Path(args.output))
    print(f"total_cases={summary.total_cases}")
    print(f"pass_rate={summary.pass_rate:.4f}")
    if args.fail_on_error and summary.failed_cases:
        raise SystemExit(1)


if __name__ == "__main__":
    main()
