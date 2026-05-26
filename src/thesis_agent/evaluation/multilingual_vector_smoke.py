"""CLI-friendly multilingual vector smoke checks."""

from __future__ import annotations

import json
from dataclasses import asdict, dataclass, field
from pathlib import Path

from thesis_agent.pipeline.retrieval import search_vector_index


@dataclass
class MultilingualVectorSmokeCase:
    case_id: str
    query: str
    language: str = "ja"
    top_k: int = 3


@dataclass
class MultilingualVectorSmokeResult:
    case_id: str
    query: str
    language: str
    result_count: int
    ok: bool
    warnings: list[str] = field(default_factory=list)


@dataclass
class MultilingualVectorSmokeSummary:
    total_cases: int
    passed_cases: int
    failed_cases: int
    pass_rate: float
    results: list[MultilingualVectorSmokeResult]
    metadata: dict = field(default_factory=dict)


def load_multilingual_vector_smoke_cases(path: Path) -> list[MultilingualVectorSmokeCase]:
    cases: list[MultilingualVectorSmokeCase] = []
    if not path.exists():
        return cases
    with path.open("r", encoding="utf-8") as handle:
        for line in handle:
            if line.strip():
                data = json.loads(line)
                allowed = {key: data[key] for key in data if key in MultilingualVectorSmokeCase.__dataclass_fields__}
                cases.append(MultilingualVectorSmokeCase(**allowed))
    return cases


def evaluate_multilingual_vector_smoke(
    *,
    cases: list[MultilingualVectorSmokeCase],
    vector_persist_dir: Path,
    vector_collection: str = "thesis_agent_demo",
    embedding_provider: str = "hash",
) -> MultilingualVectorSmokeSummary:
    results: list[MultilingualVectorSmokeResult] = []
    for case in cases:
        try:
            hits = search_vector_index(vector_persist_dir, case.query, top_k=case.top_k, collection_name=vector_collection, embedding_provider_name=embedding_provider)
            warnings: list[str] = []
        except Exception as exc:
            hits = []
            warnings = [str(exc)]
        results.append(MultilingualVectorSmokeResult(case_id=case.case_id, query=case.query, language=case.language, result_count=len(hits), ok=bool(hits), warnings=warnings))
    total = len(results)
    passed = sum(1 for result in results if result.ok)
    return MultilingualVectorSmokeSummary(total_cases=total, passed_cases=passed, failed_cases=total - passed, pass_rate=passed / total if total else 0.0, results=results, metadata={"embedding_provider": embedding_provider})


def write_multilingual_vector_smoke_summary(summary: MultilingualVectorSmokeSummary, output_path: Path) -> None:
    output_path.parent.mkdir(parents=True, exist_ok=True)
    output_path.write_text(json.dumps(asdict(summary), ensure_ascii=False, indent=2), encoding="utf-8")
