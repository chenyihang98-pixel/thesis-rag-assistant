"""Search the local vector index."""

from __future__ import annotations

import argparse
from pathlib import Path

from thesis_agent.pipeline.retrieval import search_vector_index


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Search a local hash vector index.")
    parser.add_argument("--persist-dir", default="data/vector/chroma")
    parser.add_argument("--collection", default="thesis_agent_demo")
    parser.add_argument("--query", required=True)
    parser.add_argument("--top-k", type=int, default=5)
    parser.add_argument("--embedding-provider", default="hash")
    return parser


def main() -> None:
    args = build_parser().parse_args()
    results = search_vector_index(Path(args.persist_dir), args.query, top_k=args.top_k, collection_name=args.collection, embedding_provider_name=args.embedding_provider)
    for result in results:
        print(f"{result.rank}\t{result.score:.4f}\t{result.citation}\t{result.title}")


if __name__ == "__main__":
    main()
