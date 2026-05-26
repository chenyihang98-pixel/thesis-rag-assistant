"""Lightweight Agent schemas for local orchestration."""

from __future__ import annotations

from dataclasses import dataclass, field


@dataclass
class AgentIntent:
    task: str
    query: str
    confidence: float = 1.0
    metadata: dict = field(default_factory=dict)


@dataclass
class AgentToolSpec:
    name: str
    description: str
    requires_external_access: bool = False
    is_private_data_safe: bool = True
    metadata: dict = field(default_factory=dict)


@dataclass
class AgentToolResult:
    tool_name: str
    ok: bool
    data: dict = field(default_factory=dict)
    warnings: list[str] = field(default_factory=list)
    errors: list[str] = field(default_factory=list)
    metadata: dict = field(default_factory=dict)


@dataclass
class AgentState:
    query: str
    task: str = "auto"
    intent: AgentIntent | None = None
    tool_results: list[AgentToolResult] = field(default_factory=list)
    warnings: list[str] = field(default_factory=list)
    errors: list[str] = field(default_factory=list)
    metadata: dict = field(default_factory=dict)


@dataclass
class AgentRunResult:
    ok: bool
    task: str
    intent: str
    query: str
    final_answer: str = ""
    citations: list[str] = field(default_factory=list)
    warnings: list[str] = field(default_factory=list)
    errors: list[str] = field(default_factory=list)
    state: AgentState | None = None
    tool_results: list[AgentToolResult] = field(default_factory=list)
    metadata: dict = field(default_factory=dict)
