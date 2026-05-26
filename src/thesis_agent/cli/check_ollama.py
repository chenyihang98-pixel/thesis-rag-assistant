"""Local Ollama health check CLI."""

from __future__ import annotations

import argparse
import json
import urllib.request


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Check a local Ollama server.")
    parser.add_argument("--base-url", default="http://localhost:11434")
    parser.add_argument("--model", default="")
    parser.add_argument("--timeout", type=int, default=10)
    parser.add_argument("--chat-test", action="store_true")
    parser.add_argument("--think", action="store_true")
    return parser


def main() -> None:
    args = build_parser().parse_args()
    tags_url = args.base_url.rstrip("/") + "/api/tags"
    with urllib.request.urlopen(tags_url, timeout=args.timeout) as response:
        payload = json.loads(response.read().decode("utf-8"))
    models = [item.get("name", "") for item in payload.get("models", [])]
    print("ok=true")
    print("models=" + ", ".join(models))
    if args.model:
        print(f"model_available={str(args.model in models).lower()}")


if __name__ == "__main__":
    main()
