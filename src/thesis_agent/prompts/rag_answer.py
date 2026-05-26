"""Prompt builders for grounded RAG answers."""

from __future__ import annotations

from thesis_agent.llm.providers import LLMMessage
from thesis_agent.pipeline.citations import (
    CitationRegistryEntry,
    build_citation_registry,
    format_citation_registry_for_prompt,
)


def _language_rule(language: str) -> str:
    normalized = (language or "zh").lower()
    if normalized == "zh":
        return (
            "Answer language: zh\n"
            "You must answer in Simplified Chinese.\n"
            "检索片段可能是日文，但你必须翻译并用简体中文总结。\n"
            "不要让回答正文跟随检索片段语言；不要用日文写正文。\n"
            "Only paper titles, Citation IDs, and [1]/[2]/[3] aliases may remain in the original language."
        )
    if normalized == "en":
        return (
            "Answer language: en\n"
            "You must answer in English.\n"
            "Retrieved snippets may be Japanese, but the answer body must be English.\n"
            "Even if retrieved context is Japanese, translate and summarize it in English.\n"
            "Do not write the answer body in Japanese.\n"
            "Citation IDs, [1]/[2]/[3], and original titles may remain unchanged."
        )
    if normalized == "ja":
        return (
            "Answer language: ja\n"
            "日本語で回答してください。\n"
            "引用番号 [1]/[2]/[3]、Citation ID、論文タイトルは必要に応じて原文のまま保持してください。"
        )
    return "Answer in the requested user language and keep citation IDs unchanged."


def _format_contexts(registry: list[CitationRegistryEntry], retrieved_contexts: list[dict], max_context_chars: int) -> str:
    context_lines = [
        "Allowed Citation Registry:",
        format_citation_registry_for_prompt(registry),
        "",
        "Retrieved Contexts:",
    ]
    total = 0
    for entry, context in zip(registry, retrieved_contexts):
        snippet = str(context.get("snippet") or context.get("display_text") or context.get("text") or "")
        remaining = max(max_context_chars - total, 0)
        snippet = snippet[:remaining]
        total += len(snippet)
        context_lines.extend(
            [
                f"{entry.alias}",
                f"Citation: {entry.citation}",
                f"Title: {entry.title}",
                f"Snippet: {snippet}",
                "",
            ]
        )
        if total >= max_context_chars:
            break
    return "\n".join(context_lines)


def build_rag_answer_messages(
    user_query: str,
    retrieved_contexts: list[dict],
    language: str = "zh",
    max_context_chars: int = 6000,
) -> list[LLMMessage]:
    registry = build_citation_registry(retrieved_contexts)
    system = (
        "You are a thesis knowledge-base assistant.\n"
        "Answer only from the retrieved contexts.\n"
        "Use only listed citation aliases such as [1], [2], [3] or their canonical citations.\n"
        "Do not use unlisted numbers. Do not invent papers or citations.\n"
        "Every major claim should include at least one citation alias.\n"
        "If evidence is insufficient, say so.\n"
        "Do not perform plagiarism detection. Do not ghostwrite a thesis or promise to finish a thesis.\n"
        "Do not output chain-of-thought, hidden reasoning, or <think> blocks. Output final answer only.\n\n"
        + _language_rule(language)
    )
    user = (
        f"User question:\n{user_query}\n\n"
        "Required output format:\n"
        "## Answer\n"
        "- Answer with citations.\n\n"
        "## Uncertainty\n"
        "- Mention uncertainty if evidence is incomplete.\n\n"
        + _format_contexts(registry, retrieved_contexts, max_context_chars)
    )
    return [LLMMessage(role="system", content=system), LLMMessage(role="user", content=user)]


def build_missing_citation_retry_messages(
    *,
    user_query: str,
    previous_answer_markdown: str,
    citation_registry: list[CitationRegistryEntry],
    language: str,
) -> list[LLMMessage]:
    system = (
        "The previous answer is invalid because it did not contain an allowed retrieved citation.\n"
        "Rewrite the answer using ONLY the allowed citation aliases/canonical citations listed below.\n"
        "You must include at least one valid citation alias such as [1], [2], or [3].\n"
        "Do not invent citations. Do not output reasoning or <think> blocks.\n\n"
        + _language_rule(language)
    )
    user = (
        f"User question:\n{user_query}\n\n"
        "Previous answer:\n"
        f"{previous_answer_markdown}\n\n"
        "Allowed Citation Registry:\n"
        f"{format_citation_registry_for_prompt(citation_registry)}"
    )
    return [LLMMessage(role="system", content=system), LLMMessage(role="user", content=user)]


def build_language_rewrite_messages(
    *,
    previous_answer_markdown: str,
    citation_registry: list[CitationRegistryEntry],
    target_language: str,
    strict: bool = False,
) -> list[LLMMessage]:
    normalized = (target_language or "zh").lower()
    if normalized == "en":
        rewrite_rule = (
            "Target answer language: en\n"
            "Rewrite the answer body in English.\n"
            "Preserve [1]/[2]/[3] citation aliases.\n"
            "Preserve Citation IDs.\n"
            "Do not add new facts.\n"
            "Do not remove citations.\n"
            "Do not write Japanese body text.\n"
            "Original paper titles in references may remain unchanged, but the answer body must be English.\n"
        )
        if strict:
            rewrite_rule += (
                "Strict retry: output only English answer body sections and citations.\n"
                "Do not keep any Japanese sentences from the previous answer.\n"
            )
    elif normalized == "ja":
        rewrite_rule = (
            "Target answer language: ja\n"
            "回答本文を日本語に整えてください。\n"
            "[1]/[2]/[3] の引用番号と Citation ID は保持してください。\n"
            "新しい事実を追加しないでください。\n"
            "引用を削除しないでください。\n"
        )
    else:
        rewrite_rule = (
            "Target answer language: zh\n"
            "请将正文改写为简体中文。\n"
            "不要使用日文正文。\n"
            "保留 [1]/[2]/[3] 引用编号。\n"
            "保留 Citation ID。\n"
            "不添加新事实。\n"
            "不删除引用。\n"
            "论文标题和参考依据中的原始标题可以保留原文，但回答正文必须是中文。\n"
        )
        if strict:
            rewrite_rule += (
                "严格重试：只输出简体中文正文和引用。\n"
                "不要保留上一版中的任何日文句子。\n"
            )
    system = (
        "You are rewriting a previously generated RAG answer to satisfy the requested answer language.\n"
        "This is an answer-only rewrite. Do not use or request original retrieved context.\n"
        "Do not output chain-of-thought, hidden reasoning, or <think> blocks.\n\n"
        + rewrite_rule
    )
    user = (
        "Previous answer markdown:\n"
        f"{previous_answer_markdown}\n\n"
        "Allowed Citation Registry / Reference Mapping:\n"
        f"{format_citation_registry_for_prompt(citation_registry)}"
    )
    return [LLMMessage(role="system", content=system), LLMMessage(role="user", content=user)]
