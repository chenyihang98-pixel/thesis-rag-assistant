"""Convenience CLI for local Ollama RAG answer eval."""

from __future__ import annotations

import json
import os
from pathlib import Path

from thesis_agent.cli.evaluate_rag_answers import build_parser
from thesis_agent.evaluation.rag_answer_eval import evaluate_rag_answer_cases, load_rag_answer_cases, write_rag_answer_eval_summary

OLLAMA_MODEL_NOT_CONFIGURED = (
    "Ollama model is not configured. Pass --ollama-model, set OLLAMA_MODEL, "
    "or run scripts/configure_llm.ps1."
)


def main() -> None:
    parser = build_parser()
    parser.set_defaults(llm_provider="ollama", output="outputs/eval/rag_answer_eval_ollama.json")
    parser.add_argument("--config", default="data/evaluation/ollama_rag_answer_eval_config.json")
    args = parser.parse_args()
    config = json.loads(Path(args.config).read_text(encoding="utf-8")) if Path(args.config).exists() else {}
    ollama_model = args.ollama_model or config.get("ollama_model") or os.getenv("OLLAMA_MODEL")
    if not ollama_model:
        parser.error(OLLAMA_MODEL_NOT_CONFIGURED)
    cases = load_rag_answer_cases(Path(args.cases))
    summary = evaluate_rag_answer_cases(
        cases,
        tfidf_index_path=Path(args.tfidf_index),
        vector_persist_dir=Path(args.vector_persist_dir),
        vector_collection=args.vector_collection,
        embedding_provider=args.embedding_provider or config.get("embedding_provider", "hash"),
        llm_provider="ollama",
        ollama_base_url=args.ollama_base_url or config.get("ollama_base_url", "http://localhost:11434"),
        ollama_model=ollama_model,
        top_k=args.top_k or config.get("top_k"),
        language=args.language or None,
    )
    write_rag_answer_eval_summary(summary, Path(args.output))
    print(f"total_cases={summary.total_cases}")
    print(f"passed_cases={summary.passed_cases}")
    print(f"failed_cases={summary.failed_cases}")
    print(f"pass_rate={summary.pass_rate:.4f}")
    print(f"output={args.output}")
    if args.fail_on_error and summary.failed_cases:
        raise SystemExit(1)


if __name__ == "__main__":
    main()
