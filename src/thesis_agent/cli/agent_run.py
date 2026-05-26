"""Run the local ThesisAgent orchestrator from the CLI."""

from __future__ import annotations

import argparse
import os
from pathlib import Path

from thesis_agent.agent.orchestrator import AgentOrchestrator

OLLAMA_MODEL_NOT_CONFIGURED = (
    "Ollama model is not configured. Pass --ollama-model, set OLLAMA_MODEL, "
    "or run scripts/configure_llm.ps1."
)


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Run local ThesisAgent tasks.")
    parser.add_argument("--task", default="auto", choices=["auto", "search", "topic_analysis", "topic", "structure_check", "structure", "report", "rag_answer"])
    parser.add_argument("--query", required=True)
    parser.add_argument("--index", default="data/index/tfidf_index.pkl")
    parser.add_argument("--top-k", type=int, default=5)
    parser.add_argument("--language", default="ja", choices=["ja", "zh", "en"])
    parser.add_argument("--sample-path", default="")
    parser.add_argument("--retrieval-mode", default="hybrid", choices=["tfidf", "vector", "hybrid"])
    parser.add_argument("--llm-provider", default="mock", choices=["mock", "ollama", "api"])
    parser.add_argument("--vector-persist-dir", default="data/vector/chroma")
    parser.add_argument("--vector-collection", default="thesis_agent_demo")
    parser.add_argument("--embedding-provider", default="hash")
    parser.add_argument("--ollama-base-url", default="http://localhost:11434")
    parser.add_argument("--ollama-model", default=None)
    parser.add_argument("--ollama-timeout-seconds", type=int, default=90)
    parser.add_argument("--ollama-temperature", type=float, default=0.2)
    parser.add_argument("--ollama-num-ctx", type=int, default=2048)
    parser.add_argument("--api-base-url", default="")
    parser.add_argument("--api-model", default="")
    parser.add_argument("--api-key", default="")
    parser.add_argument("--output", default="")
    return parser


def main() -> None:
    parser = build_parser()
    args = parser.parse_args()
    ollama_model = args.ollama_model or os.getenv("OLLAMA_MODEL")
    if args.llm_provider == "ollama" and not ollama_model:
        parser.error(OLLAMA_MODEL_NOT_CONFIGURED)
    result = AgentOrchestrator().run(
        query=args.query,
        task=args.task,
        index_path=Path(args.index),
        tfidf_index_path=Path(args.index),
        top_k=args.top_k,
        language=args.language,
        sample_path=Path(args.sample_path) if args.sample_path else None,
        retrieval_mode=args.retrieval_mode,
        llm_provider_name=args.llm_provider,
        vector_persist_dir=Path(args.vector_persist_dir),
        vector_collection=args.vector_collection,
        embedding_provider_name=args.embedding_provider,
        ollama_base_url=args.ollama_base_url,
        ollama_model=ollama_model,
        ollama_timeout_seconds=args.ollama_timeout_seconds,
        ollama_temperature=args.ollama_temperature,
        ollama_num_ctx=args.ollama_num_ctx,
        api_base_url=args.api_base_url or None,
        api_model=args.api_model or None,
        api_key=args.api_key or None,
    )
    if args.output and result.final_answer:
        output = Path(args.output)
        output.parent.mkdir(parents=True, exist_ok=True)
        output.write_text(result.final_answer, encoding="utf-8")
    print(f"intent={result.intent}")
    print(f"ok={result.ok}")
    print(f"citations={len(result.citations)}")
    print(f"warnings={len(result.warnings)}")
    if args.output:
        print(f"output={args.output}")
    if result.errors:
        for error in result.errors:
            print(f"error={error}")


if __name__ == "__main__":
    main()
