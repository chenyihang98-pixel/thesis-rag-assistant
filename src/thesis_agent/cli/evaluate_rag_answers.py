"""Evaluate grounded RAG answers."""

from __future__ import annotations

import argparse
import os
from pathlib import Path

from thesis_agent.evaluation.rag_answer_eval import evaluate_rag_answer_cases, load_rag_answer_cases, write_rag_answer_eval_summary

OLLAMA_MODEL_NOT_CONFIGURED = (
    "Ollama model is not configured. Pass --ollama-model, set OLLAMA_MODEL, "
    "or run scripts/configure_llm.ps1."
)


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Evaluate RAG answer quality on synthetic cases.")
    parser.add_argument("--cases", default="data/evaluation/rag_answer_cases.jsonl")
    parser.add_argument("--tfidf-index", default="data/index/structured_tfidf_index.pkl")
    parser.add_argument("--vector-persist-dir", default="data/vector/chroma")
    parser.add_argument("--vector-collection", default="thesis_agent_demo")
    parser.add_argument("--embedding-provider", default="hash")
    parser.add_argument("--llm-provider", default="mock", choices=["mock", "ollama", "api"])
    parser.add_argument("--ollama-base-url", default="http://localhost:11434")
    parser.add_argument("--ollama-model", default=None)
    parser.add_argument("--top-k", type=int, default=0)
    parser.add_argument("--language", default="")
    parser.add_argument("--output", default="outputs/eval/rag_answer_eval.json")
    parser.add_argument("--fail-on-error", action="store_true")
    return parser


def main() -> None:
    parser = build_parser()
    args = parser.parse_args()
    ollama_model = args.ollama_model or os.getenv("OLLAMA_MODEL")
    if args.llm_provider == "ollama" and not ollama_model:
        parser.error(OLLAMA_MODEL_NOT_CONFIGURED)
    cases = load_rag_answer_cases(Path(args.cases))
    summary = evaluate_rag_answer_cases(
        cases,
        tfidf_index_path=Path(args.tfidf_index),
        vector_persist_dir=Path(args.vector_persist_dir),
        vector_collection=args.vector_collection,
        embedding_provider=args.embedding_provider,
        llm_provider=args.llm_provider,
        ollama_base_url=args.ollama_base_url,
        ollama_model=ollama_model,
        top_k=args.top_k or None,
        language=args.language or None,
    )
    write_rag_answer_eval_summary(summary, Path(args.output))
    print(f"total_cases={summary.total_cases}")
    print(f"passed_cases={summary.passed_cases}")
    print(f"failed_cases={summary.failed_cases}")
    print(f"pass_rate={summary.pass_rate:.4f}")
    print(f"citation_rate={summary.citation_rate:.4f}")
    print(f"output={args.output}")
    if args.fail_on_error and summary.failed_cases:
        raise SystemExit(1)


if __name__ == "__main__":
    main()
