"""Check an embedding provider without contacting external services by default."""

from __future__ import annotations

import argparse

from thesis_agent.embeddings.factory import get_embedding_provider


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Check an embedding provider.")
    parser.add_argument("--provider", default="hash")
    parser.add_argument("--model", default="")
    parser.add_argument("--text", default="RAGを用いた卒業論文支援")
    return parser


def main() -> None:
    args = build_parser().parse_args()
    provider = get_embedding_provider(args.provider, model_name=args.model)
    vector = provider.embed_text(args.text)
    print(f"provider={provider.provider_name}")
    print(f"dimensions={len(vector)}")


if __name__ == "__main__":
    main()
