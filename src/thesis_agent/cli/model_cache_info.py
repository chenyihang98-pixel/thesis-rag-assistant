"""Print local model/cache guidance without downloading models."""

from __future__ import annotations

import argparse
from pathlib import Path


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Show local model cache hints.")
    parser.add_argument("--provider", default="sentence-transformer")
    parser.add_argument("--model", default="sentence-transformers/paraphrase-multilingual-MiniLM-L12-v2")
    return parser


def main() -> None:
    args = build_parser().parse_args()
    print(f"provider={args.provider}")
    print(f"model={args.model}")
    print(f"home_cache={(Path.home() / '.cache').as_posix()}")
    print("downloaded=false")


if __name__ == "__main__":
    main()
