"""Synthetic Agent evaluation helpers."""

from __future__ import annotations

import json
from dataclasses import asdict, dataclass, field
from pathlib import Path

from thesis_agent.agent.orchestrator import AgentOrchestrator


@dataclass
class AgentEvalCase:
    case_id: str
    query: str
    task: str = "search"
    expect_ok: bool = True
    required_terms: list[str] = field(default_factory=list)
    top_k: int = 3
    language: str = "ja"
    notes: str = ""


@dataclass
class AgentEvalResult:
    case_id: str
    ok: bool
    query: str
    task: str
    intent: str
    missing_required_terms: list[str] = field(default_factory=list)
    warnings: list[str] = field(default_factory=list)
    errors: list[str] = field(default_factory=list)
    metadata: dict = field(default_factory=dict)


@dataclass
class AgentEvalSummary:
    total_cases: int
    passed_cases: int
    failed_cases: int
    pass_rate: float
    results: list[AgentEvalResult]
    warnings: list[str] = field(default_factory=list)
    metadata: dict = field(default_factory=dict)


def load_eval_cases(path: Path) -> list[AgentEvalCase]:
    cases: list[AgentEvalCase] = []
    with path.open("r", encoding="utf-8") as handle:
        for line in handle:
            stripped = line.strip()
            if not stripped:
                continue
            data = json.loads(stripped)
            allowed = {key: data[key] for key in data if key in AgentEvalCase.__dataclass_fields__}
            cases.append(AgentEvalCase(**allowed))
    return cases


def evaluate_agent_case(case: AgentEvalCase, *, index_path: Path, orchestrator: AgentOrchestrator | None = None) -> AgentEvalResult:
    runner = orchestrator or AgentOrchestrator()
    run = runner.run(query=case.query, task=case.task, index_path=index_path, top_k=case.top_k, language=case.language)
    text = f"{run.final_answer}\n{run.intent}\n{' '.join(run.citations)}"
    lowered = text.lower()
    missing = [term for term in case.required_terms if term.lower() not in lowered]
    ok = run.ok == case.expect_ok
    return AgentEvalResult(
        case_id=case.case_id,
        ok=ok,
        query=case.query,
        task=case.task,
        intent=run.intent,
        missing_required_terms=missing,
        warnings=run.warnings,
        errors=run.errors,
        metadata=run.metadata,
    )


def evaluate_agent_cases(cases: list[AgentEvalCase], *, index_path: Path, orchestrator: AgentOrchestrator | None = None) -> AgentEvalSummary:
    results = [evaluate_agent_case(case, index_path=index_path, orchestrator=orchestrator) for case in cases]
    passed = sum(1 for result in results if result.ok)
    total = len(results)
    return AgentEvalSummary(
        total_cases=total,
        passed_cases=passed,
        failed_cases=total - passed,
        pass_rate=(passed / total if total else 0.0),
        results=results,
    )


def write_eval_results_jsonl(summary: AgentEvalSummary, output_path: Path) -> None:
    output_path.parent.mkdir(parents=True, exist_ok=True)
    with output_path.open("w", encoding="utf-8") as handle:
        for result in summary.results:
            handle.write(json.dumps(asdict(result), ensure_ascii=False) + "\n")
        summary_data = {key: value for key, value in asdict(summary).items() if key != "results"}
        handle.write(json.dumps({"summary": summary_data}, ensure_ascii=False) + "\n")
