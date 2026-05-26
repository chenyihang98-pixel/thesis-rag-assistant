"""Simple deterministic router for explicit Agent tasks."""

from __future__ import annotations

from thesis_agent.agent.schemas import AgentIntent

SUPPORTED_TASKS = {"search", "topic_analysis", "topic", "structure_check", "structure", "report", "rag_answer", "general_help"}


def route_intent(query: str, requested_task: str = "auto") -> AgentIntent:
    task = (requested_task or "auto").strip().lower()
    if task == "topic":
        task = "topic_analysis"
    if task == "structure":
        task = "structure_check"
    if task != "auto":
        if task not in SUPPORTED_TASKS:
            return AgentIntent(task="general_help", query=query, confidence=0.0, metadata={"unsupported_task": task})
        return AgentIntent(task=task, query=query, confidence=1.0, metadata={"requested_task": requested_task})
    if not query or not query.strip():
        return AgentIntent(task="general_help", query=query, confidence=1.0, metadata={"route": "empty_query"})
    lowered = query.lower()
    if any(token in lowered for token in ["structure", "outline", "構成", "章構成"]):
        return AgentIntent(task="structure_check", query=query, confidence=0.65, metadata={"route": "auto"})
    if any(token in lowered for token in ["topic", "theme", "選題", "テーマ"]):
        return AgentIntent(task="topic_analysis", query=query, confidence=0.65, metadata={"route": "auto"})
    return AgentIntent(task="search", query=query, confidence=0.6, metadata={"route": "auto"})
