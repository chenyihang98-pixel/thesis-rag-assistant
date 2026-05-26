"""Grounded RAG answer pipeline."""

from __future__ import annotations

import re
from dataclasses import dataclass, field
from pathlib import Path

from thesis_agent.llm.factory import get_llm_provider
from thesis_agent.llm.providers import LLMProvider, LLMResponse
from thesis_agent.llm.text_utils import strip_reasoning_text
from thesis_agent.pipeline.citations import (
    CitationValidationResult,
    build_citation_registry,
    canonicalize_answer_citations,
)
from thesis_agent.pipeline.retrieval import search_hybrid_index, search_tfidf_index, search_vector_index
from thesis_agent.prompts.rag_answer import (
    build_language_rewrite_messages,
    build_missing_citation_retry_messages,
    build_rag_answer_messages,
)


@dataclass
class RagAnswerResult:
    ok: bool
    answer_markdown: str
    query: str
    retrieval_mode: str
    llm_provider: str
    model: str | None = None
    citations: list[str] = field(default_factory=list)
    retrieved_count: int = 0
    warnings: list[str] = field(default_factory=list)
    errors: list[str] = field(default_factory=list)
    metadata: dict = field(default_factory=dict)


def extract_answer_body_for_language_check(answer_markdown: str) -> str:
    """Return answer body while ignoring reference/technical sections."""
    lines: list[str] = []
    skip = False
    skip_markers = (
        "参考依据",
        "参考文献",
        "引用",
        "出典",
        "references",
        "reference",
        "citations",
        "citation",
        "technical",
        "metadata",
    )
    for line in (answer_markdown or "").splitlines():
        stripped = line.strip().lower()
        if stripped.startswith("## "):
            skip = any(marker in stripped for marker in skip_markers)
        if not skip:
            lines.append(line)
    return "\n".join(lines)


def detect_answer_language_mismatch(answer_markdown: str, requested_language: str) -> bool:
    """Heuristic language mismatch detection for requested answer language."""
    language = (requested_language or "").lower()
    body = extract_answer_body_for_language_check(answer_markdown)
    kana = sum(1 for char in body if "\u3040" <= char <= "\u30ff")
    cjk = sum(1 for char in body if "\u3400" <= char <= "\u9fff")
    latin = sum(1 for char in body if char.isascii() and char.isalpha())
    meaningful = max(kana + cjk + latin, 1)
    if language == "zh":
        japanese_body = kana >= 3 and kana / meaningful > 0.08
        english_body = latin >= 20 and latin / meaningful > 0.70 and cjk / meaningful < 0.20
        return japanese_body or english_body
    if language == "en":
        return (kana >= 3 and kana / meaningful > 0.08) or ((kana + cjk) / meaningful > 0.25 and latin / meaningful < 0.65)
    if language == "ja":
        return latin >= 20 and latin / meaningful > 0.75 and (kana + cjk) / meaningful < 0.15
    return False


_HEADING_ALIASES = {
    "answer": {"answer", "response", "回答", "答案"},
    "uncertainty": {"uncertainty", "uncertainties", "不确定性", "不确定点", "不確実性"},
    "references": {"references", "reference", "参考依据", "参考文献"},
    "citations": {"citations", "citation", "引用"},
}

_HEADING_TITLES = {
    "zh": {
        "answer": "回答",
        "uncertainty": "不确定性",
        "references": "参考依据",
        "citations": "引用",
    },
    "en": {
        "answer": "Answer",
        "uncertainty": "Uncertainty",
        "references": "References",
        "citations": "Citations",
    },
    "ja": {
        "answer": "回答",
        "uncertainty": "不確実性",
        "references": "参考文献",
        "citations": "引用",
    },
}


def _canonical_heading_key(value: str) -> str | None:
    normalized = value.strip().strip("*").strip()
    normalized = normalized.rstrip(":：").strip().lower()
    for key, aliases in _HEADING_ALIASES.items():
        if normalized in {alias.lower() for alias in aliases}:
            return key
    return None


def normalize_answer_section_headings(answer_markdown: str, language: str) -> str:
    """Normalize standalone markdown section headings to the requested answer language."""
    titles = _HEADING_TITLES.get((language or "zh").lower(), _HEADING_TITLES["zh"])
    normalized_lines: list[str] = []
    for line in (answer_markdown or "").splitlines():
        stripped = line.strip()
        heading_match = re.match(r"^(?P<prefix>\s*#{1,6}\s+)(?P<title>.+?)(?P<suffix>\s*)$", line)
        if heading_match:
            key = _canonical_heading_key(heading_match.group("title"))
            if key:
                normalized_lines.append(f"{heading_match.group('prefix')}{titles[key]}{heading_match.group('suffix')}")
                continue

        bold_match = re.match(r"^(?P<indent>\s*)\*\*(?P<title>.+?)\*\*(?P<colon>[:：]?)(?P<suffix>\s*)$", line)
        if bold_match:
            key = _canonical_heading_key(bold_match.group("title"))
            if key:
                normalized_lines.append(
                    f"{bold_match.group('indent')}**{titles[key]}**{bold_match.group('colon')}{bold_match.group('suffix')}"
                )
                continue

        plain_match = re.match(r"^(?P<indent>\s*)(?P<title>[^:：]{1,40})(?P<colon>[:：]?)(?P<suffix>\s*)$", line)
        if plain_match:
            key = _canonical_heading_key(plain_match.group("title") + plain_match.group("colon"))
            if key:
                normalized_lines.append(
                    f"{plain_match.group('indent')}{titles[key]}{plain_match.group('colon')}{plain_match.group('suffix')}"
                )
                continue

        normalized_lines.append(line)
    return "\n".join(normalized_lines)


def _contexts_from_results(results: list) -> list[dict]:
    contexts: list[dict] = []
    for index, item in enumerate(results, start=1):
        metadata = dict(item.metadata or {})
        metadata["score"] = item.score
        metadata["rank"] = item.rank
        metadata["source_type"] = "retrieval"
        metadata["source_mapping"] = {
            "alias": f"[{index}]",
            "visible_rank": None,
            "retrieval_rank": index,
            "title": item.title,
            "citation": item.citation,
            "score": item.score,
            "source_type": "retrieval",
        }
        contexts.append(
            {
            "title": item.title,
            "citation": item.citation,
            "snippet": item.text,
            "doc_id": item.doc_id,
            "chunk_id": item.chunk_id,
            "metadata": metadata,
            }
        )
    return contexts


def _source_mappings_from_contexts(contexts: list[dict], *, source_type: str) -> list[dict]:
    mappings: list[dict] = []
    for index, context in enumerate(contexts, start=1):
        metadata = context.get("metadata") or {}
        mapping = dict(metadata.get("source_mapping") or {})
        mapping.setdefault("alias", f"[{index}]")
        mapping.setdefault("title", context.get("title", ""))
        mapping.setdefault("citation", context.get("citation", ""))
        mapping.setdefault("score", metadata.get("score"))
        mapping.setdefault("source_type", source_type)
        mapping.setdefault(
            "source_item",
            {
                "rank": mapping.get("retrieval_rank") or mapping.get("visible_rank") or index,
                "title": context.get("title", ""),
                "citation": context.get("citation", ""),
                "score": mapping.get("score"),
                "snippet": context.get("snippet", ""),
                "doc_id": context.get("doc_id", ""),
                "chunk_id": context.get("chunk_id", ""),
                "metadata": metadata,
            },
        )
        if mapping.get("source_type") == "retrieval":
            mapping.setdefault("retrieval_rank", index)
            mapping.setdefault("visible_rank", None)
        else:
            mapping.setdefault("visible_rank", metadata.get("rank", index))
            mapping.setdefault("retrieval_rank", None)
        mappings.append(mapping)
    return mappings


def _dedupe_warning(warnings: list[str], warning: str) -> None:
    if warning not in warnings:
        warnings.append(warning)


def _canonicalize(
    answer: str,
    contexts: list[dict],
    *,
    append_reference_section: bool,
    language: str = "zh",
) -> tuple[str, CitationValidationResult]:
    registry = build_citation_registry(contexts)
    return canonicalize_answer_citations(
        answer,
        registry,
        append_reference_section=append_reference_section,
        language=language,
    )


def generate_rag_answer(
    *,
    query: str,
    retrieval_mode: str = "hybrid",
    llm_provider_name: str = "mock",
    llm_provider: LLMProvider | None = None,
    language: str = "zh",
    top_k: int = 5,
    tfidf_index_path: Path | None = None,
    vector_persist_dir: Path | None = None,
    vector_collection: str = "thesis_agent_demo",
    embedding_provider_name: str = "hash",
    model_name: str | None = None,
    ollama_base_url: str = "http://localhost:11434",
    ollama_model: str | None = None,
    ollama_timeout_seconds: int = 90,
    ollama_temperature: float = 0.2,
    ollama_num_ctx: int = 2048,
    ollama_think: bool = False,
    api_base_url: str | None = None,
    api_model: str | None = None,
    api_key: str | None = None,
    api_timeout_seconds: int = 90,
    api_temperature: float = 0.2,
    api_max_tokens: int = 1200,
    provided_contexts: list[dict] | None = None,
    context_source: str | None = None,
    retry_missing_citations: bool = True,
    max_citation_retries: int = 1,
    append_citation_reference_section: bool = True,
    retry_language_mismatch: bool = True,
    max_language_retries: int = 2,
) -> RagAnswerResult:
    del model_name
    warnings: list[str] = []
    try:
        contexts = list(provided_contexts or [])
        source = context_source or ("provided_contexts" if contexts else "retrieval")
        if contexts:
            contexts = contexts[:top_k]
        else:
            if retrieval_mode in {"hybrid", "vector"} and not vector_persist_dir:
                _dedupe_warning(warnings, "vector_index_unavailable_fallback_to_tfidf")
                retrieval_mode = "tfidf"
            if tfidf_index_path is None:
                raise ValueError("tfidf_index_path is required when no provided_contexts are supplied")
            if retrieval_mode == "vector":
                if vector_persist_dir is None:
                    raise ValueError("vector_persist_dir is required for vector retrieval")
                try:
                    results = search_vector_index(
                        vector_persist_dir,
                        query=query,
                        top_k=top_k,
                        collection_name=vector_collection,
                        embedding_provider_name=embedding_provider_name,
                    )
                except Exception:
                    _dedupe_warning(warnings, "vector_index_unavailable_fallback_to_tfidf")
                    retrieval_mode = "tfidf"
                    results = search_tfidf_index(tfidf_index_path, query=query, top_k=top_k)
            elif retrieval_mode == "hybrid":
                if vector_persist_dir and vector_persist_dir.exists():
                    try:
                        results = search_hybrid_index(
                            tfidf_index_path=tfidf_index_path,
                            vector_persist_dir=vector_persist_dir,
                            query=query,
                            top_k=top_k,
                            vector_collection=vector_collection,
                            embedding_provider_name=embedding_provider_name,
                        )
                    except Exception:
                        _dedupe_warning(warnings, "vector_index_unavailable_fallback_to_tfidf")
                        retrieval_mode = "tfidf"
                        results = search_tfidf_index(tfidf_index_path, query=query, top_k=top_k)
                else:
                    _dedupe_warning(warnings, "vector_index_unavailable_fallback_to_tfidf")
                    retrieval_mode = "tfidf"
                    results = search_tfidf_index(tfidf_index_path, query=query, top_k=top_k)
            else:
                results = search_tfidf_index(tfidf_index_path, query=query, top_k=top_k)
            contexts = _contexts_from_results(results)

        provider = llm_provider or get_llm_provider(
            llm_provider_name,
            model=ollama_model,
            ollama_base_url=ollama_base_url,
            ollama_timeout_seconds=ollama_timeout_seconds,
            ollama_temperature=ollama_temperature,
            ollama_num_ctx=ollama_num_ctx,
            ollama_think=ollama_think,
            api_base_url=api_base_url,
            api_model=api_model,
            api_key=api_key,
            api_timeout_seconds=api_timeout_seconds,
            api_temperature=api_temperature,
            api_max_tokens=api_max_tokens,
        )
        registry = build_citation_registry(contexts)
        source_mappings = _source_mappings_from_contexts(contexts, source_type=source)

        response: LLMResponse = provider.generate(build_rag_answer_messages(query, contexts, language=language))
        answer = strip_reasoning_text(response.content)
        answer, citation_result = canonicalize_answer_citations(
            answer,
            registry,
            append_reference_section=append_citation_reference_section,
            language=language,
        )
        answer = normalize_answer_section_headings(answer, language)

        citation_retry_count = 0
        citation_recovery_method = ""
        while (
            citation_result.missing_citation
            and retry_missing_citations
            and citation_retry_count < max(0, max_citation_retries)
        ):
            citation_retry_count += 1
            response = provider.generate(
                build_missing_citation_retry_messages(
                    user_query=query,
                    previous_answer_markdown=answer,
                    citation_registry=registry,
                    language=language,
                )
            )
            answer = strip_reasoning_text(response.content)
            answer, citation_result = canonicalize_answer_citations(
                answer,
                registry,
                append_reference_section=append_citation_reference_section,
                language=language,
            )
            answer = normalize_answer_section_headings(answer, language)
            citation_recovery_method = "retry"

        language_retry_count = 0
        language_rewrite_prompt_kind = ""
        initial_language_mismatch = detect_answer_language_mismatch(answer, language)
        language_mismatch = initial_language_mismatch
        if language_mismatch and retry_language_mismatch and max_language_retries > 0:
            _dedupe_warning(warnings, "answer_language_mismatch")
            _dedupe_warning(warnings, "answer_language_retry_applied")
            while language_mismatch and language_retry_count < max(0, max_language_retries):
                prompt_kind = "strict" if language_retry_count > 0 else "standard"
                language_retry_count += 1
                language_rewrite_prompt_kind = prompt_kind
                response = provider.generate(
                    build_language_rewrite_messages(
                        previous_answer_markdown=answer,
                        citation_registry=registry,
                        target_language=language,
                        strict=prompt_kind == "strict",
                    )
                )
                answer = strip_reasoning_text(response.content)
                answer, citation_result = canonicalize_answer_citations(
                    answer,
                    registry,
                    append_reference_section=append_citation_reference_section,
                    language=language,
                )
                answer = normalize_answer_section_headings(answer, language)
                language_mismatch = detect_answer_language_mismatch(answer, language)

        answer = normalize_answer_section_headings(answer, language)

        if citation_result.missing_citation:
            _dedupe_warning(warnings, "answer_contains_no_retrieved_citation")
        if citation_result.resolved_aliases:
            _dedupe_warning(warnings, "citation_aliases_resolved")
        if citation_result.citation_appendix_added:
            _dedupe_warning(warnings, "citation_appendix_added")
        if citation_result.unknown_aliases:
            _dedupe_warning(warnings, "unknown_citation_aliases")
        if language_mismatch:
            _dedupe_warning(warnings, "answer_language_still_mismatch")

        return RagAnswerResult(
            ok=True,
            answer_markdown=answer,
            query=query,
            retrieval_mode=retrieval_mode,
            llm_provider=response.provider,
            model=response.model,
            citations=citation_result.canonical_citations,
            retrieved_count=len(contexts),
            warnings=warnings,
            metadata={
                "context_source": source,
                "provided_context_count": len(provided_contexts or []),
                "ai_context_count": len(contexts),
                "visible_result_count": len(provided_contexts or []),
                "source_mappings": source_mappings,
                "citation_retry_count": citation_retry_count,
                "citation_recovery_method": citation_recovery_method,
                "resolved_aliases": citation_result.resolved_aliases,
                "citation_appendix_added": citation_result.citation_appendix_added,
                "unknown_aliases": citation_result.unknown_aliases,
                "hallucinated_citations": citation_result.hallucinated_citations,
                "requested_language": language,
                "requested_language_effective": language,
                "language_match": not language_mismatch,
                "language_retry_count": language_retry_count,
                "language_rewrite_applied": language_retry_count > 0,
                "language_rewrite_mode": "answer_only" if language_retry_count > 0 else "",
                "language_rewrite_prompt_kind": language_rewrite_prompt_kind,
                "language_mismatch_detected": initial_language_mismatch,
            },
        )
    except Exception as exc:
        return RagAnswerResult(
            ok=False,
            answer_markdown="",
            query=query,
            retrieval_mode=retrieval_mode,
            llm_provider=llm_provider_name,
            errors=[str(exc)],
            warnings=warnings,
        )
