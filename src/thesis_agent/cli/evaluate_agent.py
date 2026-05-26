"""Evaluate local Agent behavior on synthetic cases."""

from __future__ import annotations

import argparse
from pathlib import Path

from thesis_agent.evaluation.agent_eval import evaluate_agent_cases, load_eval_cases, write_eval_results_jsonl


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Evaluate ThesisAgent local Agent behavior.")
    parser.add_argument("--cases", default="data/evaluation/agent_golden_queries.jsonl")
    parser.add_argument("--index", default="data/index/tfidf_index.pkl")
    parser.add_argument("--output", default="outputs/eval/agent_eval_results.jsonl")
    parser.add_argument("--language", default="ja")
    parser.add_argument("--fail-on-error", action="store_true")
    return parser


def main() -> None:
    args = build_parser().parse_args()
    cases = load_eval_cases(Path(args.cases))
    for case in cases:
        if not case.language:
            case.language = args.language
    summary = evaluate_agent_cases(cases, index_path=Path(args.index))
    write_eval_results_jsonl(summary, Path(args.output))
    print(f"total_cases={summary.total_cases}")
    print(f"passed_cases={summary.passed_cases}")
    print(f"failed_cases={summary.failed_cases}")
    print(f"pass_rate={summary.pass_rate:.4f}")
    print(f"output={args.output}")
    if args.fail_on_error and summary.failed_cases:
        raise SystemExit(1)


if __name__ == "__main__":
    main()
