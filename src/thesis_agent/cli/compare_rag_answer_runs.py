"""Compare two RAG answer eval summaries."""

from __future__ import annotations

import argparse
from pathlib import Path

from thesis_agent.evaluation.rag_answer_comparison import compare_rag_answer_runs, load_rag_answer_eval_summary, write_rag_answer_run_comparison


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Compare baseline and candidate RAG answer runs.")
    parser.add_argument("--baseline", default="outputs/eval/rag_answer_eval.json")
    parser.add_argument("--candidate", default="outputs/eval/rag_answer_eval_ollama.json")
    parser.add_argument("--output", default="outputs/eval/rag_answer_run_comparison.json")
    return parser


def main() -> None:
    args = build_parser().parse_args()
    report = compare_rag_answer_runs(load_rag_answer_eval_summary(Path(args.baseline)), load_rag_answer_eval_summary(Path(args.candidate)))
    write_rag_answer_run_comparison(report, Path(args.output))
    print(f"total_cases={report.total_cases}")
    print(f"compared_cases={report.compared_cases}")
    print(f"baseline_pass_rate={report.baseline_pass_rate:.4f}")
    print(f"candidate_pass_rate={report.candidate_pass_rate:.4f}")
    print(f"citation_overlap_avg={report.citation_overlap_avg:.4f}")
    print(f"candidate_regression_cases={','.join(report.candidate_regression_cases)}")
    print(f"output={args.output}")


if __name__ == "__main__":
    main()
