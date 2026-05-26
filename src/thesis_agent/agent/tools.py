"""Default tool registry for the local Agent."""

from __future__ import annotations

from thesis_agent.agent.schemas import AgentToolSpec


def get_default_tool_specs() -> list[AgentToolSpec]:
    return [
        AgentToolSpec(name="search", description="Search similar thesis chunks from local indexes."),
        AgentToolSpec(name="topic_analysis", description="Analyze topic overlap and risk from local retrieval."),
        AgentToolSpec(name="structure_check", description="Check thesis structure completeness for safe local samples."),
        AgentToolSpec(name="report", description="Generate a deterministic local topic report."),
        AgentToolSpec(
            name="rag_answer",
            description="Generate a grounded RAG answer from retrieved thesis chunks. Requires explicit task.",
            requires_external_access=False,
            is_private_data_safe=True,
        ),
    ]
