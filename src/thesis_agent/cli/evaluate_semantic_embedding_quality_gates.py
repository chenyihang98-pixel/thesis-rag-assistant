"""Evaluate semantic embedding comparison quality gates."""

from __future__ import annotations

import argparse
import json
from pathlib import Path

from thesis_agent.evaluation.semantic_embedding_quality_gates import evaluate_semantic_embedding_quality_gates, load_semantic_embedding_quality_config, write_semantic_embedding_quality_report


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Evaluate semantic embedding comparison gates.")
    parser.add_argument("--semantic-summary", default="outputs/eval/semantic_embedding_comparison.json")
    parser.add_argument("--config", default="data/evaluation/semantic_embedding_quality_gates.json")
    parser.add_argument("--output", default="outputs/eval/semantic_embedding_quality_report.json")
    parser.add_argument("--fail-on-error", action="store_true")
    return parser


def main() -> None:
    args = build_parser().parse_args()
    summary = json.loads(Path(args.semantic_summary).read_text(encoding="utf-8"))
    gates = evaluate_semantic_embedding_quality_gates(summary, load_semantic_embedding_quality_config(Path(args.config)))
    write_semantic_embedding_quality_report(gates, Path(args.output))
    print(f"ok={gates.ok}")
    if args.fail_on_error and not gates.ok:
        raise SystemExit(1)


if __name__ == "__main__":
    main()
