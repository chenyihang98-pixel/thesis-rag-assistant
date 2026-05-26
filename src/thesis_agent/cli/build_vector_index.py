"""Build a lightweight local vector index for demo and internal runtime assets."""

from __future__ import annotations

import argparse
from pathlib import Path

from thesis_agent.vectorstore.chroma import build_vector_index


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Build a lightweight demo vector index placeholder.")
    parser.add_argument("--chunks", required=True)
    parser.add_argument("--persist-dir", required=True)
    parser.add_argument("--collection", default="thesis_agent_demo")
    parser.add_argument("--embedding-provider", default="hash")
    parser.add_argument("--embedding-model", default="")
    parser.add_argument("--reset", action="store_true")
    return parser


def main() -> None:
    args = build_parser().parse_args()
    stats = build_vector_index(
        chunks_path=Path(args.chunks),
        persist_dir=Path(args.persist_dir),
        collection_name=args.collection,
        embedding_provider_name=args.embedding_provider,
        embedding_model=args.embedding_model,
        reset=args.reset,
    )
    for key in ["chunk_count", "collection_count", "collection_name", "persist_dir", "embedding_provider", "model_name", "reset"]:
        print(f"{key}={stats[key]}")


if __name__ == "__main__":
    main()
