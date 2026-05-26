"""Search local TF-IDF and vector indexes together."""

from __future__ import annotations

import argparse
from pathlib import Path

from thesis_agent.pipeline.retrieval import search_hybrid_index


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Run local hybrid retrieval.")
    parser.add_argument("--tfidf-index", default="data/index/structured_tfidf_index.pkl")
    parser.add_argument("--vector-persist-dir", default="data/vector/chroma")
    parser.add_argument("--vector-collection", default="thesis_agent_demo")
    parser.add_argument("--query", required=True)
    parser.add_argument("--top-k", type=int, default=5)
    parser.add_argument("--embedding-provider", default="hash")
    return parser


def main() -> None:
    args = build_parser().parse_args()
    results = search_hybrid_index(
        tfidf_index_path=Path(args.tfidf_index),
        vector_persist_dir=Path(args.vector_persist_dir),
        query=args.query,
        top_k=args.top_k,
        vector_collection=args.vector_collection,
        embedding_provider_name=args.embedding_provider,
    )
    for result in results:
        print(f"{result.rank}\t{result.score:.4f}\t{result.citation}\t{result.title}")


if __name__ == "__main__":
    main()
