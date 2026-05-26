"""Evaluate retrieval mode quality gates."""

from __future__ import annotations

import argparse
import json
from pathlib import Path

from thesis_agent.evaluation.retrieval_quality_gates import evaluate_retrieval_quality_gates, load_retrieval_quality_config, write_retrieval_quality_report


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Evaluate retrieval quality gates.")
    parser.add_argument("--retrieval-summary", default="outputs/eval/retrieval_mode_eval.json")
    parser.add_argument("--config", default="data/evaluation/retrieval_mode_quality_gates.json")
    parser.add_argument("--output", default="outputs/eval/retrieval_quality_report.json")
    parser.add_argument("--fail-on-error", action="store_true")
    return parser


def main() -> None:
    args = build_parser().parse_args()
    summary = json.loads(Path(args.retrieval_summary).read_text(encoding="utf-8"))
    gates = evaluate_retrieval_quality_gates(summary, load_retrieval_quality_config(Path(args.config)))
    write_retrieval_quality_report(gates, Path(args.output))
    print(f"ok={gates.ok}")
    print(f"failed_gates={gates.failed_gates}")
    if args.fail_on_error and not gates.ok:
        raise SystemExit(1)


if __name__ == "__main__":
    main()
