"""Run multilingual vector smoke evaluation."""

from __future__ import annotations

import argparse
from pathlib import Path

from thesis_agent.evaluation.multilingual_vector_smoke import evaluate_multilingual_vector_smoke, load_multilingual_vector_smoke_cases, write_multilingual_vector_smoke_summary


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Evaluate multilingual vector smoke cases.")
    parser.add_argument("--cases", default="data/evaluation/multilingual_vector_smoke_queries.jsonl")
    parser.add_argument("--vector-persist-dir", default="data/vector/chroma")
    parser.add_argument("--vector-collection", default="thesis_agent_demo")
    parser.add_argument("--embedding-provider", default="hash")
    parser.add_argument("--output", default="outputs/eval/multilingual_vector_smoke.json")
    parser.add_argument("--fail-on-error", action="store_true")
    return parser


def main() -> None:
    args = build_parser().parse_args()
    summary = evaluate_multilingual_vector_smoke(cases=load_multilingual_vector_smoke_cases(Path(args.cases)), vector_persist_dir=Path(args.vector_persist_dir), vector_collection=args.vector_collection, embedding_provider=args.embedding_provider)
    write_multilingual_vector_smoke_summary(summary, Path(args.output))
    print(f"total_cases={summary.total_cases}")
    print(f"pass_rate={summary.pass_rate:.4f}")
    if args.fail_on_error and summary.failed_cases:
        raise SystemExit(1)


if __name__ == "__main__":
    main()
