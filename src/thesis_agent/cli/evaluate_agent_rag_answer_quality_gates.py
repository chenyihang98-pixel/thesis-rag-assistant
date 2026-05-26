"""Evaluate Agent RAG answer quality gates."""

from __future__ import annotations

import argparse
import json
from pathlib import Path

from thesis_agent.evaluation.agent_rag_answer_quality_gates import evaluate_agent_rag_answer_quality_gates, load_agent_rag_answer_quality_config, write_agent_rag_answer_quality_report


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Evaluate Agent RAG answer quality gates.")
    parser.add_argument("--agent-rag-answer-summary", default="outputs/eval/agent_rag_answer_eval.json")
    parser.add_argument("--config", default="data/evaluation/agent_rag_answer_quality_gates.json")
    parser.add_argument("--output", default="outputs/eval/agent_rag_answer_quality_report.json")
    parser.add_argument("--fail-on-error", action="store_true")
    return parser


def main() -> None:
    args = build_parser().parse_args()
    summary = json.loads(Path(args.agent_rag_answer_summary).read_text(encoding="utf-8"))
    config = load_agent_rag_answer_quality_config(Path(args.config))
    report = evaluate_agent_rag_answer_quality_gates(summary, config)
    write_agent_rag_answer_quality_report(report, Path(args.output))
    print(f"ok={report.ok}")
    print(f"passed_gates={report.passed_gates}")
    print(f"failed_gates={report.failed_gates}")
    print(f"output={args.output}")
    if args.fail_on_error and not report.ok:
        raise SystemExit(1)


if __name__ == "__main__":
    main()
