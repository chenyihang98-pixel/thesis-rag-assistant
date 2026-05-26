"""Tool runner for local Agent tasks."""

from __future__ import annotations

from pathlib import Path

from thesis_agent.agent.schemas import AgentToolResult
from thesis_agent.llm.mock import MockLLM
from thesis_agent.pipeline.rag_answer import generate_rag_answer
from thesis_agent.tools.search import search_thesis
from thesis_agent.tools.structure import analyze_structure_file, analyze_structure_text
from thesis_agent.tools.topic import compare_topic


def run_tool(tool_name: str, **kwargs) -> AgentToolResult:
    name = (tool_name or "").strip().lower()
    try:
        if name == "search":
            result = search_thesis(
                index_path=Path(kwargs["index_path"]),
                query=kwargs["query"],
                top_k=int(kwargs.get("top_k", 5)),
                allow_pii_query=bool(kwargs.get("allow_pii_query", False)),
            )
            return AgentToolResult(tool_name=name, ok=result.ok, data=result.data, warnings=result.warnings, errors=result.errors)
        if name in {"topic", "topic_analysis", "report"}:
            result = compare_topic(
                index_path=Path(kwargs["index_path"]),
                topic=kwargs["query"],
                top_k=int(kwargs.get("top_k", 5)),
                allow_pii_query=bool(kwargs.get("allow_pii_query", False)),
            )
            data = dict(result.data)
            if name == "report" and result.ok:
                data["report_markdown"] = MockLLM().generate_topic_report(
                    topic=kwargs["query"],
                    topic_analysis=result.data,
                    search_results=result.data.get("references", []),
                    language=kwargs.get("language", "ja"),
                )
            return AgentToolResult(tool_name=name, ok=result.ok, data=data, warnings=result.warnings, errors=result.errors)
        if name in {"structure", "structure_check"}:
            sample_path = kwargs.get("sample_path")
            if sample_path:
                result = analyze_structure_file(Path(sample_path), language=kwargs.get("language", "ja"))
            else:
                result = analyze_structure_text(kwargs.get("query", ""), language=kwargs.get("language", "ja"))
            return AgentToolResult(tool_name="structure_check", ok=result.ok, data=result.data, warnings=result.warnings, errors=result.errors)
        if name == "rag_answer":
            rag = generate_rag_answer(
                query=kwargs["query"],
                retrieval_mode=kwargs.get("retrieval_mode", "hybrid"),
                llm_provider_name=kwargs.get("llm_provider_name") or kwargs.get("llm_provider", "mock"),
                language=kwargs.get("language", "zh"),
                top_k=int(kwargs.get("top_k", 3)),
                tfidf_index_path=Path(kwargs.get("tfidf_index_path") or kwargs.get("index_path")),
                vector_persist_dir=Path(kwargs["vector_persist_dir"]) if kwargs.get("vector_persist_dir") else None,
                vector_collection=kwargs.get("vector_collection", "thesis_agent_demo"),
                embedding_provider_name=kwargs.get("embedding_provider_name") or kwargs.get("embedding_provider", "hash"),
                ollama_base_url=kwargs.get("ollama_base_url", "http://localhost:11434"),
                ollama_model=kwargs.get("ollama_model"),
                ollama_timeout_seconds=int(kwargs.get("ollama_timeout_seconds", 90)),
                ollama_temperature=float(kwargs.get("ollama_temperature", 0.2)),
                ollama_num_ctx=int(kwargs.get("ollama_num_ctx", 2048)),
                api_base_url=kwargs.get("api_base_url"),
                api_model=kwargs.get("api_model"),
                api_key=kwargs.get("api_key"),
            )
            return AgentToolResult(
                tool_name="rag_answer",
                ok=rag.ok,
                data={
                    "answer_markdown": rag.answer_markdown,
                    "citations": rag.citations,
                    "retrieved_count": rag.retrieved_count,
                    "retrieval_mode": rag.retrieval_mode,
                    "llm_provider": rag.llm_provider,
                    "model": rag.model,
                    "metadata": rag.metadata,
                },
                warnings=rag.warnings,
                errors=rag.errors,
            )
        return AgentToolResult(tool_name=name, ok=False, errors=[f"Unsupported tool: {tool_name}"])
    except Exception as exc:
        return AgentToolResult(tool_name=name, ok=False, errors=[str(exc)])
