"""Thin local Agent orchestrator."""

from __future__ import annotations

from thesis_agent.agent.router import route_intent
from thesis_agent.agent.schemas import AgentRunResult, AgentState
from thesis_agent.agent.tool_runner import run_tool


class AgentOrchestrator:
    """Route explicit tasks to local tools and return a unified result."""

    def run(self, *, query: str, task: str = "auto", **kwargs) -> AgentRunResult:
        intent = route_intent(query=query, requested_task=task)
        state = AgentState(query=query, task=task, intent=intent)
        if intent.task == "general_help":
            return AgentRunResult(
                ok=True,
                task=task,
                intent=intent.task,
                query=query,
                final_answer="Please choose a supported task: search, topic_analysis, structure_check, report, or rag_answer.",
                state=state,
            )
        tool_result = run_tool(intent.task, query=query, **kwargs)
        state.tool_results.append(tool_result)
        state.warnings.extend(tool_result.warnings)
        state.errors.extend(tool_result.errors)
        final_answer = _final_answer_for_tool(intent.task, tool_result.data)
        citations = tool_result.data.get("citations", [])
        metadata = {
            "retrieved_count": tool_result.data.get("retrieved_count", len(tool_result.data.get("results", []))),
            "retrieval_mode": tool_result.data.get("retrieval_mode", kwargs.get("retrieval_mode", "")),
            "llm_provider": tool_result.data.get("llm_provider", kwargs.get("llm_provider", kwargs.get("llm_provider_name", ""))),
        }
        return AgentRunResult(
            ok=tool_result.ok,
            task=task,
            intent=intent.task,
            query=query,
            final_answer=final_answer,
            citations=citations,
            warnings=tool_result.warnings,
            errors=tool_result.errors,
            state=state,
            tool_results=[tool_result],
            metadata=metadata,
        )


def _final_answer_for_tool(task: str, data: dict) -> str:
    if task == "rag_answer":
        return data.get("answer_markdown", "")
    if task == "report":
        return data.get("report_markdown", "")
    if task == "search":
        results = data.get("results", [])
        lines = ["# Search Results", ""]
        for result in results:
            lines.append(f"- {result.get('title', 'Untitled')} ({result.get('citation', '')})")
        return "\n".join(lines)
    if task == "topic_analysis":
        return f"Risk level: {data.get('risk_level', 'unknown')} ({data.get('risk_score', 0.0)})"
    if task == "structure_check":
        return f"Structure score: {data.get('score', 0.0)}"
    return ""
