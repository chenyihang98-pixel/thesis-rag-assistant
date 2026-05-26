"""CLI for local grounded RAG answers."""

from __future__ import annotations

import argparse
import os
from pathlib import Path

from thesis_agent.pipeline.rag_answer import generate_rag_answer

OLLAMA_MODEL_NOT_CONFIGURED = (
    "Ollama model is not configured. Pass --ollama-model, set OLLAMA_MODEL, "
    "or run scripts/configure_llm.ps1."
)


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Generate a local grounded RAG answer.")
    parser.add_argument("--query", required=True)
    parser.add_argument("--retrieval-mode", choices=("tfidf", "vector", "hybrid"), default="hybrid")
    parser.add_argument("--llm-provider", choices=("mock", "ollama", "api"), default="mock")
    parser.add_argument("--tfidf-index", default="data/index/structured_tfidf_index.pkl")
    parser.add_argument("--vector-persist-dir", default="data/vector/chroma")
    parser.add_argument("--vector-collection", default="thesis_agent_demo")
    parser.add_argument("--embedding-provider", default="hash")
    parser.add_argument("--top-k", type=int, default=5)
    parser.add_argument("--language", choices=("zh", "ja", "en"), default="zh")
    parser.add_argument("--ollama-base-url", default="http://localhost:11434")
    parser.add_argument("--ollama-model", default=None)
    parser.add_argument("--ollama-timeout-seconds", type=int, default=90)
    parser.add_argument("--ollama-temperature", type=float, default=0.2)
    parser.add_argument("--ollama-num-ctx", type=int, default=2048)
    parser.add_argument("--api-base-url", default="")
    parser.add_argument("--api-model", default="")
    parser.add_argument("--api-key", default="")
    parser.add_argument("--api-timeout-seconds", type=int, default=90)
    parser.add_argument("--api-temperature", type=float, default=0.2)
    parser.add_argument("--api-max-tokens", type=int, default=1200)
    parser.add_argument("--retry-missing-citations", dest="retry_missing_citations", action="store_true", default=True)
    parser.add_argument("--no-retry-missing-citations", dest="retry_missing_citations", action="store_false")
    parser.add_argument("--max-citation-retries", type=int, default=1)
    parser.add_argument("--append-citation-reference-section", dest="append_citation_reference_section", action="store_true", default=True)
    parser.add_argument("--no-append-citation-reference-section", dest="append_citation_reference_section", action="store_false")
    parser.add_argument("--retry-language-mismatch", dest="retry_language_mismatch", action="store_true", default=True)
    parser.add_argument("--no-retry-language-mismatch", dest="retry_language_mismatch", action="store_false")
    parser.add_argument("--max-language-retries", type=int, default=2)
    parser.add_argument("--output", default="")
    parser.add_argument("--fail-on-error", action="store_true")
    return parser


def main() -> None:
    parser = build_parser()
    args = parser.parse_args()
    ollama_model = args.ollama_model or os.getenv("OLLAMA_MODEL")
    if args.llm_provider == "ollama" and not ollama_model:
        parser.error(OLLAMA_MODEL_NOT_CONFIGURED)
    result = generate_rag_answer(
        query=args.query,
        retrieval_mode=args.retrieval_mode,
        llm_provider_name=args.llm_provider,
        language=args.language,
        top_k=args.top_k,
        tfidf_index_path=Path(args.tfidf_index),
        vector_persist_dir=Path(args.vector_persist_dir) if args.vector_persist_dir else None,
        vector_collection=args.vector_collection,
        embedding_provider_name=args.embedding_provider,
        ollama_base_url=args.ollama_base_url,
        ollama_model=ollama_model,
        ollama_timeout_seconds=args.ollama_timeout_seconds,
        ollama_temperature=args.ollama_temperature,
        ollama_num_ctx=args.ollama_num_ctx,
        api_base_url=args.api_base_url,
        api_model=args.api_model,
        api_key=args.api_key,
        api_timeout_seconds=args.api_timeout_seconds,
        api_temperature=args.api_temperature,
        api_max_tokens=args.api_max_tokens,
        retry_missing_citations=args.retry_missing_citations,
        max_citation_retries=args.max_citation_retries,
        append_citation_reference_section=args.append_citation_reference_section,
        retry_language_mismatch=args.retry_language_mismatch,
        max_language_retries=args.max_language_retries,
    )
    if args.output and result.answer_markdown:
        output = Path(args.output)
        output.parent.mkdir(parents=True, exist_ok=True)
        output.write_text(result.answer_markdown, encoding="utf-8")
    print(result.answer_markdown)
    if result.citations:
        print("citations=" + ", ".join(result.citations))
    if result.warnings:
        print("warnings=" + ", ".join(result.warnings))
    if result.errors:
        print("errors=" + "; ".join(result.errors))
    if args.fail_on_error and not result.ok:
        raise SystemExit(1)


if __name__ == "__main__":
    main()
