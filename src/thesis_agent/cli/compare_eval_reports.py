"""Compare two rendered evaluation report JSON files."""

from __future__ import annotations

import argparse
import json
from pathlib import Path

from thesis_agent.evaluation.reporting import EvaluationReport, compare_evaluation_reports


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Compare two evaluation report JSON files.")
    parser.add_argument("--left", required=True)
    parser.add_argument("--right", required=True)
    parser.add_argument("--output", default="")
    return parser


def _load(path: Path) -> EvaluationReport:
    data = json.loads(path.read_text(encoding="utf-8"))
    allowed = {key: data.get(key) for key in EvaluationReport.__dataclass_fields__}
    return EvaluationReport(**allowed)


def main() -> None:
    args = build_parser().parse_args()
    result = compare_evaluation_reports(_load(Path(args.left)), _load(Path(args.right)))
    if args.output:
        output = Path(args.output)
        output.parent.mkdir(parents=True, exist_ok=True)
        output.write_text(json.dumps(result, ensure_ascii=False, indent=2), encoding="utf-8")
        print(f"output={args.output}")
    else:
        print(json.dumps(result, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
