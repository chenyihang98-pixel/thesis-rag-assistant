"""网页层服务函数，负责检索、选题分析、结构检查、PDF 操作和结果整理。"""

from __future__ import annotations

import hashlib
import json
import os
import time
from pathlib import Path

import streamlit as st

from thesis_agent.corpus.catalog import catalog_by_doc_id, load_catalog, sync_catalog
from thesis_agent.llm.mock import MockLLM
from thesis_agent.kb_snapshot import (
    load_kb_snapshot_manifest,
    load_snapshot_history,
    load_snapshot_records,
    resolve_snapshot_history_path,
    resolve_snapshot_manifest_path,
    resolve_snapshot_record_dir,
)
from thesis_agent.pipeline.ingest import ingest_documents
from thesis_agent.pipeline.rag_answer import generate_rag_answer
from thesis_agent.pipeline.retrieval import (
    build_tfidf_index,
    search_hybrid_index,
    search_tfidf_index,
    search_vector_index,
)
from thesis_agent.privacy.pii import scan_pii
from thesis_agent.retrieval.io import load_chunks_jsonl
from thesis_agent.retrieval.models import SearchResult
from thesis_agent.retrieval.tfidf import TfidfRetriever
from thesis_agent.tools.schemas import ToolResult
from thesis_agent.tools.structure import analyze_structure_file
from thesis_agent.tools.topic import (
    RISK_HIGH_THRESHOLD,
    RISK_MEDIUM_THRESHOLD,
    _build_recommendations,
    risk_level_from_score,
)
from thesis_agent.ui.pdf_actions import read_pdf_bytes


WORKSPACE_ROOT = Path.cwd().resolve()
FORBIDDEN_PARTS = {"raw", "private", "anonymized"}
ROUTINE_AI_WARNINGS = {
    "using_current_search_results",
    "using_topic_candidates",
    "citation_aliases_resolved",
    "citation_appendix_added",
    "current_search_results_truncated_to_top_k",
    "ai_context_count_clamped_to_visible_results",
    "ai_context_count_clamped_to_eligible_results",
    "low_quality_contexts_omitted",
    "structured_index_missing_fallback_to_standard_index",
    "structured_chunks_missing_fallback_to_standard_chunks",
    "ai_retrieval_top_k_clamped_for_provider",
    "ai_retrieval_returned_fewer_sources_than_requested",
    "ai_context_truncated_to_budget",
    "vector_index_unavailable_fallback_to_tfidf",
    "answer_language_mismatch",
    "answer_language_retry_applied",
}
IMPORTANT_AI_WARNINGS = {
    "answer_language_still_mismatch",
    "answer_contains_no_retrieved_citation",
    "unknown_citation_aliases",
    "no_current_search_results_fallback_to_retrieval",
    "no_topic_candidates_fallback_to_retrieval",
    "no_current_search_results_choose_retrieval",
    "no_topic_candidates_choose_retrieval",
}
RUNTIME_LLM_PROVIDER_CHOICES = ("ollama", "api")
DEV_LLM_PROVIDER_CHOICES = ("mock", "ollama", "api")
OLLAMA_BASE_URL_EXAMPLE = "http://localhost:11434"


def get_runtime_llm_provider_choices() -> tuple[str, ...]:
    """Return user-facing runtime providers shown in the Streamlit UI."""
    return RUNTIME_LLM_PROVIDER_CHOICES


def get_dev_llm_provider_choices() -> tuple[str, ...]:
    """Return all providers available to CLI, tests, and evaluation."""
    return DEV_LLM_PROVIDER_CHOICES


def normalize_runtime_provider(provider: str | None) -> str:
    """Normalize stale/unknown UI provider values to the runtime default."""
    normalized = (provider or "").strip().lower()
    if normalized in RUNTIME_LLM_PROVIDER_CHOICES:
        return normalized
    return "ollama"


def _env_float(name: str, default: float) -> float:
    value = os.getenv(name, "").strip()
    if not value:
        return default
    try:
        return float(value)
    except ValueError:
        return default


def _env_int(name: str, default: int) -> int:
    value = os.getenv(name, "").strip()
    if not value:
        return default
    try:
        return int(value)
    except ValueError:
        return default


def get_llm_profile_defaults_from_env() -> dict:
    """Return local LLM defaults exported by scripts/run_* from the ignored profile."""
    provider = normalize_runtime_provider(os.getenv("LLM_DEFAULT_PROVIDER", "ollama"))
    profile_name = os.getenv("LLM_PROFILE_NAME", "").strip()
    configured = bool(
        profile_name
        or os.getenv("OLLAMA_MODEL", "").strip()
        or os.getenv("API_LLM_MODEL", "").strip()
        or os.getenv("API_LLM_API_KEY", "").strip()
    )
    return {
        "llm_profile_configured": configured,
        "llm_profile_name": profile_name,
        "provider": provider,
        "llm_provider": provider,
        "ollama_base_url": os.getenv("OLLAMA_BASE_URL", "").strip(),
        "ollama_model": os.getenv("OLLAMA_MODEL", "").strip(),
        "ollama_temperature": _env_float("OLLAMA_TEMPERATURE", 0.2),
        "ollama_num_ctx": _env_int("OLLAMA_NUM_CTX", 4096),
        "ollama_num_predict": _env_int("OLLAMA_NUM_PREDICT", 1200),
        "api_base_url": os.getenv("API_LLM_BASE_URL", "").strip(),
        "api_model": os.getenv("API_LLM_MODEL", "").strip(),
        "api_key": os.getenv("API_LLM_API_KEY", "").strip(),
        "api_temperature": _env_float("API_LLM_TEMPERATURE", 0.2),
        "api_max_tokens": _env_int("API_LLM_MAX_TOKENS", 2000),
    }


def _path_from_optional(value: Path | str | None) -> Path:
    if value is None:
        return Path()
    if isinstance(value, Path):
        return value
    if not str(value).strip():
        return Path()
    return Path(value)


def resolve_internal_tfidf_index_path(
    *,
    structured_index_path: Path | str | None,
    standard_index_path: Path | str | None,
) -> dict:
    """Resolve the internal TF-IDF index path with structured-to-standard fallback."""
    structured = _path_from_optional(structured_index_path)
    standard = _path_from_optional(standard_index_path)
    if str(structured) and structured.exists():
        return {"path": structured, "warnings": [], "errors": [], "used_fallback": False}
    if str(standard) and standard.exists():
        warnings = ["structured_index_missing_fallback_to_standard_index"] if str(structured) else []
        return {"path": standard, "warnings": warnings, "errors": [], "used_fallback": bool(str(structured))}
    attempted = [str(path) for path in (structured, standard) if str(path)]
    attempted_text = "; ".join(attempted) if attempted else "LAB_STRUCTURED_INDEX_PATH / LAB_INDEX_PATH"
    return {
        "path": standard if str(standard) else structured,
        "warnings": [],
        "errors": [f"Internal TF-IDF index is unavailable. Checked: {attempted_text}"],
        "used_fallback": False,
    }


def resolve_internal_chunks_path(
    *,
    structured_chunks_path: Path | str | None,
    standard_chunks_path: Path | str | None,
) -> dict:
    """Resolve the internal chunks path with structured-to-standard fallback."""
    structured = _path_from_optional(structured_chunks_path)
    standard = _path_from_optional(standard_chunks_path)
    if str(structured) and structured.exists():
        return {"path": structured, "warnings": [], "errors": [], "used_fallback": False}
    if str(standard) and standard.exists():
        warnings = ["structured_chunks_missing_fallback_to_standard_chunks"] if str(structured) else []
        return {"path": standard, "warnings": warnings, "errors": [], "used_fallback": bool(str(structured))}
    attempted = [str(path) for path in (structured, standard) if str(path)]
    attempted_text = "; ".join(attempted) if attempted else "LAB_STRUCTURED_CHUNKS_PATH / LAB_CHUNKS_PATH"
    return {
        "path": standard if str(standard) else structured,
        "warnings": [],
        "errors": [f"Internal chunks file is unavailable. Checked: {attempted_text}"],
        "used_fallback": False,
    }


def get_ai_retrieval_top_k_limit(provider: str) -> int:
    """Return provider-specific UI cap for AI new retrieval paper count."""
    normalized = (provider or "").strip().lower()
    if normalized == "api":
        return 10
    return 5


def clamp_ai_retrieval_top_k_for_provider(requested: int, provider: str) -> tuple[int, bool, int]:
    """Clamp AI retrieval paper count to the provider-dependent safety cap."""
    limit = get_ai_retrieval_top_k_limit(provider)
    requested_count = int(requested or 1)
    clamped = max(1, min(requested_count, limit))
    return clamped, clamped != requested_count, limit


def max_chunks_per_paper_for_provider(provider: str) -> int:
    """Return per-paper chunk budget for AI new retrieval prompts."""
    return 3 if (provider or "").strip().lower() == "api" else 2


def context_budget_chars_for_provider(provider: str) -> int:
    """Return total snippet character budget for AI new retrieval prompts."""
    return 16000 if (provider or "").strip().lower() == "api" else 8000


def build_ollama_timeout_user_message(labels: dict[str, str]) -> str:
    """Return a friendly local Ollama timeout message for visible UI errors."""
    return labels.get(
        "ollama_timeout_message",
        "Local Ollama timed out. Lower AI retrieval Top K, use current visible results, or switch to API.",
    )


def maybe_replace_timeout_errors(result: dict, *, provider: str, labels: dict[str, str]) -> dict:
    """Replace visible Ollama timeout errors while preserving raw errors in metadata."""
    if (provider or "").strip().lower() != "ollama":
        return result
    raw_errors = list(result.get("errors") or [])
    if not any("timed out" in str(error).lower() or "timeout" in str(error).lower() for error in raw_errors):
        return result
    updated = dict(result)
    metadata = dict(updated.get("metadata") or {})
    metadata["raw_errors"] = raw_errors
    updated["metadata"] = metadata
    updated["errors"] = [build_ollama_timeout_user_message(labels)]
    return updated


def max_current_context_count(visible_count: int, global_top_k: int | None = None) -> int:
    """Return the maximum AI context count allowed for currently visible items."""
    visible = max(0, int(visible_count or 0))
    if global_top_k is None:
        return visible
    return min(visible, max(0, int(global_top_k or 0)))


def clamp_ai_context_count(
    requested_count: int,
    *,
    visible_count: int,
    global_top_k: int | None = None,
) -> tuple[int, bool]:
    """Clamp a requested current-result context count to visible/global limits."""
    maximum = max_current_context_count(visible_count, global_top_k)
    if maximum <= 0:
        return 0, int(requested_count or 0) != 0
    requested = int(requested_count or maximum)
    clamped = max(1, min(requested, maximum))
    return clamped, clamped != requested


def clamp_context_count(requested: int, available: int) -> tuple[int, bool]:
    """Clamp a context count to the currently available visible items."""
    return clamp_ai_context_count(requested, visible_count=available)


def is_ai_eligible_context(item: dict) -> tuple[bool, str]:
    """Return whether a visible result is suitable as default AI context."""
    score = item.get("score")
    if score is not None:
        try:
            if float(score) <= 0:
                return False, "score_zero"
        except (TypeError, ValueError):
            pass
    if not extract_paper_snippet_preview(item):
        return False, "empty_snippet"
    if not item.get("citation"):
        return False, "missing_citation"
    return True, "ok"


def filter_ai_eligible_contexts(
    results: list[dict] | None,
    *,
    include_low_similarity_contexts: bool = False,
) -> tuple[list[dict], list[dict]]:
    """Filter visible results to contexts suitable for AI current-result mode."""
    eligible: list[dict] = []
    omitted: list[dict] = []
    for item in results or []:
        ok, reason = is_ai_eligible_context(item)
        if ok:
            eligible.append(item)
        elif include_low_similarity_contexts and reason == "score_zero":
            if not extract_paper_snippet_preview(item):
                omitted.append({"item": item, "reason": "empty_snippet"})
            elif not item.get("citation"):
                omitted.append({"item": item, "reason": "missing_citation"})
            else:
                eligible.append(item)
        else:
            omitted.append({"item": item, "reason": reason})
    return eligible, omitted


def build_ai_source_mappings(
    items: list[dict] | None,
    *,
    source_type: str,
    limit: int | None = None,
) -> list[dict]:
    """Build the visible source mapping shown under generated AI answers."""
    selected = list(items or [])
    if limit is not None:
        selected = selected[: max(0, int(limit))]
    mappings: list[dict] = []
    for index, item in enumerate(selected, start=1):
        rank = item.get("rank")
        try:
            visible_rank = int(rank) if rank not in (None, "") else index
        except (TypeError, ValueError):
            visible_rank = index
        score = item.get("score")
        source_item = dict(item)
        source_item.setdefault("rank", index)
        source_item.setdefault("score", score)
        mappings.append(
            {
                "alias": f"[{index}]",
                "visible_rank": visible_rank if source_type != "retrieval" else None,
                "retrieval_rank": index if source_type == "retrieval" else None,
                "paper_id": item.get("paper_id") or get_paper_identity(item),
                "title": item.get("title") or item.get("doc_id") or "",
                "citation": item.get("representative_citation") or item.get("citation") or "",
                "score": score,
                "source_type": source_type,
                "used_chunk_citations": list(item.get("used_chunk_citations") or []),
                "source_item": source_item,
            }
        )
    return mappings


def build_ai_sources_display_payload(source_mappings: list[dict] | None) -> dict:
    """Return compact-vs-card display data for AI source mappings."""
    mappings = list(source_mappings or [])
    if mappings and all(mapping.get("source_type") == "retrieval" for mapping in mappings):
        return {"mode": "cards", "sources": group_ai_sources_by_document(mappings)}
    return {"mode": "compact", "sources": mappings}


def _doc_id_from_source(mapping: dict) -> str:
    source_item = mapping.get("source_item") or {}
    doc_id = source_item.get("doc_id") or mapping.get("doc_id") or mapping.get("paper_id") or ""
    if doc_id:
        return str(doc_id)
    citation = str(mapping.get("citation") or source_item.get("citation") or "")
    if "#" in citation:
        return citation.split("#", 1)[0]
    return citation


def get_paper_identity(item: dict) -> str:
    """Return a stable paper identity for chunk-level retrieval results."""
    metadata = item.get("metadata") or {}
    source_item = item.get("source_item") or {}
    for candidate in (
        item.get("doc_id"),
        metadata.get("doc_id"),
        source_item.get("doc_id"),
    ):
        if candidate:
            return str(candidate)
    citation = str(item.get("citation") or source_item.get("citation") or "")
    if "#" in citation:
        return citation.split("#", 1)[0]
    title = str(item.get("title") or metadata.get("title") or source_item.get("title") or "").strip().lower()
    if title:
        return "title:" + " ".join(title.split())
    return citation


def dedupe_retrieval_results_by_paper(
    results: list[dict],
    *,
    target_paper_count: int,
    max_chunks_per_paper: int = 3,
) -> list[dict]:
    """Collapse chunk-level AI retrieval hits into paper-level sources."""
    papers: list[dict] = []
    by_paper_id: dict[str, dict] = {}
    for result in results or []:
        paper_id = get_paper_identity(result)
        if not paper_id:
            continue
        snippet = extract_paper_snippet_preview(result)
        chunk_summary = {
            "rank": result.get("rank"),
            "score": result.get("score"),
            "citation": result.get("citation", ""),
            "chunk_id": result.get("chunk_id", ""),
            "snippet": snippet,
        }
        if paper_id not in by_paper_id:
            if len(papers) >= max(0, int(target_paper_count)):
                continue
            paper = dict(result)
            paper["rank"] = len(papers) + 1
            paper["paper_id"] = paper_id
            paper["representative_citation"] = result.get("citation", "")
            paper["best_score"] = result.get("score")
            paper["score"] = result.get("score")
            paper["used_chunk_citations"] = []
            paper["used_chunks"] = []
            paper["matched_chunks"] = []
            paper["matched_chunk_count"] = 0
            by_paper_id[paper_id] = paper
            papers.append(paper)
        paper = by_paper_id[paper_id]
        try:
            current_score = float(result.get("score", 0.0) or 0.0)
            best_score = float(paper.get("best_score", 0.0) or 0.0)
            if current_score > best_score:
                paper["best_score"] = result.get("score")
                paper["score"] = result.get("score")
        except (TypeError, ValueError):
            pass
        if len(paper["used_chunks"]) < max(1, int(max_chunks_per_paper)):
            paper["used_chunks"].append(chunk_summary)
            paper["matched_chunks"].append(chunk_summary)
            if chunk_summary["citation"]:
                paper["used_chunk_citations"].append(chunk_summary["citation"])
        paper["matched_chunk_count"] = len(paper["used_chunks"])
        if not paper.get("snippet") and snippet:
            paper["snippet"] = snippet
    return papers


def _chunk_snippet_length(chunk: dict) -> int:
    return len(str(chunk.get("snippet") or chunk.get("text") or chunk.get("display_text") or ""))


def trim_ai_contexts_to_budget(
    paper_sources: list[dict],
    *,
    provider: str,
) -> tuple[list[dict], dict]:
    """Trim AI retrieval snippets to a provider-specific prompt budget."""
    budget = context_budget_chars_for_provider(provider)
    before = 0
    for paper in paper_sources or []:
        for chunk in paper.get("used_chunks") or paper.get("matched_chunks") or []:
            before += _chunk_snippet_length(chunk)
    remaining = budget
    trimmed_sources: list[dict] = []
    truncated = False
    for paper in paper_sources or []:
        copied = dict(paper)
        new_chunks: list[dict] = []
        for chunk in paper.get("used_chunks") or paper.get("matched_chunks") or []:
            snippet = str(chunk.get("snippet") or chunk.get("text") or chunk.get("display_text") or "")
            keep = min(len(snippet), max(remaining, 0))
            if keep <= 0:
                truncated = True
                continue
            chunk_copy = dict(chunk)
            if keep < len(snippet):
                truncated = True
                chunk_copy["snippet"] = snippet[:keep].rstrip()
            else:
                chunk_copy["snippet"] = snippet
            new_chunks.append(chunk_copy)
            remaining -= keep
        copied["used_chunks"] = new_chunks
        copied["matched_chunks"] = new_chunks
        copied["matched_chunk_count"] = len(new_chunks)
        copied["used_chunk_citations"] = [chunk.get("citation", "") for chunk in new_chunks if chunk.get("citation")]
        if new_chunks:
            copied["snippet"] = new_chunks[0].get("snippet", copied.get("snippet", ""))
        trimmed_sources.append(copied)
    after = 0
    for paper in trimmed_sources:
        for chunk in paper.get("used_chunks") or paper.get("matched_chunks") or []:
            after += _chunk_snippet_length(chunk)
    return trimmed_sources, {
        "context_budget_chars": budget,
        "context_chars_before_trim": before,
        "context_chars_after_trim": after,
        "context_budget_applied": truncated,
    }


def enrich_ai_retrieved_sources_with_catalog(
    sources: list[dict],
    *,
    catalog_path: Path | None,
    pdf_root: Path | None = None,
) -> list[dict]:
    """Enrich AI-retrieved source mappings with catalog metadata when available."""
    del pdf_root
    catalog = _catalog_lookup(catalog_path)
    enriched: list[dict] = []
    for source in sources or []:
        mapping = dict(source)
        source_item = dict(mapping.get("source_item") or {})
        doc_id = _doc_id_from_source(mapping)
        record = catalog.get(doc_id) if doc_id else None
        if record:
            source_item.update(
                {
                    "doc_id": record.get("doc_id", doc_id),
                    "title": record.get("title") or source_item.get("title", ""),
                    "advisor_name": record.get("advisor_name") or source_item.get("advisor_name", ""),
                    "year": record.get("year") or source_item.get("year", ""),
                    "pdf_path": record.get("pdf_path") or source_item.get("pdf_path", ""),
                    "original_filename": record.get("original_filename") or source_item.get("original_filename", ""),
                }
            )
            source_item.setdefault("metadata", {})
            source_item["metadata"] = {**dict(source_item.get("metadata") or {}), **record}
            mapping["title"] = source_item.get("title", mapping.get("title", ""))
            mapping["doc_id"] = source_item.get("doc_id", doc_id)
        elif doc_id:
            source_item.setdefault("doc_id", doc_id)
            mapping.setdefault("doc_id", doc_id)
        mapping["source_item"] = source_item
        enriched.append(mapping)
    return enriched


def group_ai_sources_by_document(sources: list[dict]) -> list[dict]:
    """Group retrieval source mappings by document while preserving alias order."""
    groups: list[dict] = []
    by_doc_key: dict[str, dict] = {}
    for index, source in enumerate(sources or [], start=1):
        source_item = dict(source.get("source_item") or {})
        doc_key = _doc_id_from_source(source) or f"{source.get('citation', '')}#{index}"
        aliases = list(source_item.get("used_aliases") or [])
        if not aliases:
            aliases = [source.get("alias") or f"[{index}]"]
        citations = list(source.get("used_chunk_citations") or source_item.get("used_chunk_citations") or source_item.get("used_citations") or [])
        if not citations and source.get("citation"):
            citations = [source.get("citation")]
        raw_chunks = list(source_item.get("used_chunks") or source_item.get("matched_chunks") or [])
        if raw_chunks:
            chunk_summaries = []
            for chunk_index, chunk in enumerate(raw_chunks):
                chunk_alias = aliases[chunk_index] if chunk_index < len(aliases) else chunk.get("alias")
                chunk_summaries.append(
                    {
                        "rank": chunk.get("rank", source.get("retrieval_rank") or index),
                        "alias": chunk_alias,
                        "score": chunk.get("score", source.get("score")),
                        "citation": chunk.get("citation", citations[chunk_index] if chunk_index < len(citations) else ""),
                        "chunk_id": chunk.get("chunk_id", ""),
                        "snippet": chunk.get("snippet", ""),
                    }
                )
        else:
            chunk_summaries = [
                {
                    "rank": source.get("retrieval_rank") or index,
                    "alias": aliases[0],
                    "score": source.get("score"),
                    "citation": source.get("citation", ""),
                    "chunk_id": source_item.get("chunk_id") or "",
                    "snippet": extract_paper_snippet_preview(source_item),
                }
            ]
        if doc_key not in by_doc_key:
            item = dict(source_item)
            item.setdefault("rank", len(groups) + 1)
            item.setdefault("doc_id", doc_key)
            item.setdefault("title", source.get("title", ""))
            item.setdefault("citation", source.get("citation", ""))
            item.setdefault("score", source.get("score"))
            item["matched_chunks"] = []
            group = dict(source)
            group["aliases"] = []
            group["citations"] = []
            group["source_item"] = item
            group["retrieval_rank"] = len(groups) + 1
            by_doc_key[doc_key] = group
            groups.append(group)
        group = by_doc_key[doc_key]
        for alias in aliases:
            if alias and alias not in group["aliases"]:
                group["aliases"].append(alias)
        for citation in citations:
            if citation and citation not in group["citations"]:
                group["citations"].append(citation)
        group["source_item"]["matched_chunks"].extend(chunk_summaries)
        group["source_item"]["matched_chunk_count"] = len(group["source_item"]["matched_chunks"])
        group["source_item"]["used_aliases"] = group["aliases"]
        group["source_item"]["used_citations"] = group["citations"]
        group["source_item"]["used_chunk_citations"] = group["citations"]
        if not group["source_item"].get("snippet"):
            for chunk_summary in chunk_summaries:
                if chunk_summary.get("snippet"):
                    group["source_item"]["snippet"] = chunk_summary["snippet"]
                    break
    return groups


def build_contexts_from_visible_results(results: list[dict], count: int) -> list[dict]:
    """Build RAG contexts from the first N currently visible search results."""
    return build_rag_contexts_from_search_results(results, top_k=count, source_type="current_search_results")


def build_contexts_from_topic_candidates(candidates: list[dict], count: int) -> list[dict]:
    """Build RAG contexts from the first N current topic candidates."""
    return build_rag_contexts_from_topic_candidates(candidates, top_k=count)


def _retrieval_result_to_item(result: SearchResult) -> dict:
    metadata = dict(result.metadata or {})
    return {
        "rank": result.rank,
        "score": round(float(result.score), 4),
        "title": metadata.get("title") or result.title,
        "citation": result.citation,
        "snippet": result.text[:300].replace("\n", " "),
        "chunk_id": result.chunk_id,
        "doc_id": result.doc_id,
        "author_name": metadata.get("author_name", ""),
        "advisor_name": metadata.get("advisor_name", ""),
        "year": metadata.get("year", ""),
        "pdf_path": metadata.get("pdf_path", ""),
        "original_filename": metadata.get("original_filename", ""),
        "metadata": metadata,
    }


def build_rag_contexts_from_paper_sources(paper_sources: list[dict]) -> list[dict]:
    """Build one RAG context per deduped paper source."""
    contexts: list[dict] = []
    mappings = build_ai_source_mappings(paper_sources, source_type="retrieval", limit=len(paper_sources))
    for index, paper in enumerate(paper_sources):
        used_chunks = list(paper.get("used_chunks") or paper.get("matched_chunks") or [])
        snippet_lines = []
        for chunk in used_chunks:
            citation = chunk.get("citation", "")
            snippet = chunk.get("snippet", "")
            if citation or snippet:
                snippet_lines.append(f"- {citation}: {snippet}".strip())
        additional_citations = [
            citation
            for citation in paper.get("used_chunk_citations", [])
            if citation and citation != paper.get("representative_citation", paper.get("citation", ""))
        ]
        if additional_citations:
            snippet_lines.append("Additional citations:")
            snippet_lines.extend(f"- {citation}" for citation in additional_citations)
        metadata = dict(paper.get("metadata") or {})
        metadata.update({key: value for key, value in paper.items() if key not in {"metadata", "snippet"}})
        if index < len(mappings):
            metadata["source_mapping"] = mappings[index]
        metadata["source_type"] = "retrieval"
        contexts.append(
            {
                "title": paper.get("title", ""),
                "citation": paper.get("representative_citation") or paper.get("citation", ""),
                "snippet": "\n".join(snippet_lines) or extract_paper_snippet_preview(paper),
                "doc_id": paper.get("doc_id", ""),
                "chunk_id": (used_chunks[0].get("chunk_id") if used_chunks else paper.get("chunk_id", "")),
                "metadata": metadata,
            }
        )
    return contexts


def retrieve_ai_paper_contexts(
    *,
    query: str,
    retrieval_mode: str,
    target_paper_count: int,
    tfidf_index_path: Path,
    vector_persist_dir: Path | None,
    vector_collection: str,
    embedding_provider: str,
    provider: str = "ollama",
) -> dict:
    """Run AI-only retrieval with chunk over-fetch and paper-level dedupe."""
    target = max(1, int(target_paper_count or 1))
    max_chunks_per_paper = max_chunks_per_paper_for_provider(provider)
    raw_top_k = min(max(target * 5, target), 40)
    warnings: list[str] = []
    effective_mode = retrieval_mode
    if retrieval_mode in {"hybrid", "vector"} and not vector_persist_dir:
        warnings.append("vector_index_unavailable_fallback_to_tfidf")
        effective_mode = "tfidf"
    if effective_mode == "vector":
        if vector_persist_dir is None:
            warnings.append("vector_index_unavailable_fallback_to_tfidf")
            effective_mode = "tfidf"
        else:
            try:
                raw_results = search_vector_index(
                    vector_persist_dir,
                    query=query,
                    top_k=raw_top_k,
                    collection_name=vector_collection,
                    embedding_provider_name=embedding_provider,
                )
            except Exception:
                warnings.append("vector_index_unavailable_fallback_to_tfidf")
                effective_mode = "tfidf"
    if effective_mode == "hybrid":
        if vector_persist_dir and vector_persist_dir.exists():
            try:
                raw_results = search_hybrid_index(
                    tfidf_index_path=tfidf_index_path,
                    vector_persist_dir=vector_persist_dir,
                    query=query,
                    top_k=raw_top_k,
                    vector_collection=vector_collection,
                    embedding_provider_name=embedding_provider,
                )
            except Exception:
                warnings.append("vector_index_unavailable_fallback_to_tfidf")
                effective_mode = "tfidf"
        else:
            warnings.append("vector_index_unavailable_fallback_to_tfidf")
            effective_mode = "tfidf"
    if effective_mode == "tfidf":
        raw_results = search_tfidf_index(tfidf_index_path, query=query, top_k=raw_top_k)
    raw_items = [_retrieval_result_to_item(result) for result in raw_results]
    paper_sources = dedupe_retrieval_results_by_paper(
        raw_items,
        target_paper_count=target,
        max_chunks_per_paper=max_chunks_per_paper,
    )
    if len(paper_sources) < target:
        warnings.append("ai_retrieval_returned_fewer_sources_than_requested")
    omitted_chunks_per_paper: dict[str, int] = {}
    for item in raw_items:
        paper_id = get_paper_identity(item)
        if not paper_id:
            continue
        raw_count = sum(1 for raw in raw_items if get_paper_identity(raw) == paper_id)
        omitted = max(0, raw_count - max_chunks_per_paper)
        if omitted:
            omitted_chunks_per_paper[paper_id] = omitted
    trimmed_sources, budget_metadata = trim_ai_contexts_to_budget(paper_sources, provider=provider)
    if budget_metadata["context_budget_applied"]:
        warnings.append("ai_context_truncated_to_budget")
    contexts = build_rag_contexts_from_paper_sources(trimmed_sources)
    return {
        "contexts": contexts,
        "paper_sources": trimmed_sources,
        "source_mappings": build_ai_source_mappings(trimmed_sources, source_type="retrieval", limit=len(trimmed_sources)),
        "warnings": warnings,
        "effective_retrieval_mode": effective_mode,
        "retrieval_target_paper_count": target,
        "retrieval_raw_chunk_count": len(raw_items),
        "retrieval_raw_chunk_top_k": raw_top_k,
        "retrieval_deduped_paper_count": len(trimmed_sources),
        "ai_retrieval_requested_top_k": target,
        "ai_retrieval_actual_source_count": len(trimmed_sources),
        "ai_retrieval_unique_paper_count": len(trimmed_sources),
        "dedupe_strategy": "paper_level_single_pass",
        "max_chunks_per_paper": max_chunks_per_paper,
        "omitted_chunks_per_paper": omitted_chunks_per_paper,
        **budget_metadata,
    }


def build_global_ai_settings(values: dict) -> dict:
    """Build effective global AI defaults from sidebar/session values.

    This helper is pure UI-state normalization. It does not call providers,
    read PDFs, or inspect runtime assets.
    """
    env_defaults = get_llm_profile_defaults_from_env()
    provider = normalize_runtime_provider(values.get("llm_provider", values.get("provider", env_defaults.get("provider", "ollama"))))
    return {
        "top_k": int(values.get("ai_top_k", values.get("top_k", 3))),
        "language_choice": values.get("answer_language_choice", "auto"),
        "language": values.get("answer_language", values.get("language", values.get("ui_language", "zh"))),
        "llm_profile_configured": bool(values.get("llm_profile_configured", env_defaults.get("llm_profile_configured", False))),
        "llm_profile_name": values.get("llm_profile_name", env_defaults.get("llm_profile_name", "")),
        "provider": provider,
        "ollama_model": values.get("ollama_model", env_defaults.get("ollama_model", "")),
        "ollama_base_url": values.get("ollama_base_url", env_defaults.get("ollama_base_url", "")),
        "ollama_temperature": float(values.get("ollama_temperature", env_defaults.get("ollama_temperature", 0.2))),
        "ollama_num_ctx": int(values.get("ollama_num_ctx", env_defaults.get("ollama_num_ctx", 4096))),
        "ollama_num_predict": int(values.get("ollama_num_predict", env_defaults.get("ollama_num_predict", 1200))),
        "api_base_url": values.get("api_base_url", env_defaults.get("api_base_url", "")),
        "api_model": values.get("api_model", env_defaults.get("api_model", "")),
        "api_key": values.get("api_key", env_defaults.get("api_key", "")),
        "api_max_tokens": int(values.get("api_max_tokens", env_defaults.get("api_max_tokens", 2000))),
        "api_temperature": float(values.get("api_temperature", env_defaults.get("api_temperature", 0.2))),
    }


def merge_ai_panel_settings(global_settings: dict, panel_settings: dict | None, override_enabled: bool) -> dict:
    """Merge panel-specific overrides over global AI settings when enabled."""
    settings = dict(global_settings)
    if override_enabled and panel_settings:
        settings.update({key: value for key, value in panel_settings.items() if value is not None})
        settings["override_enabled"] = True
    else:
        settings["override_enabled"] = False
    return settings


def _effective_model_for_settings(settings: dict) -> str:
    if settings.get("provider") == "ollama":
        return str(settings.get("ollama_model", ""))
    if settings.get("provider") == "api":
        return str(settings.get("api_model", ""))
    return str(settings.get("model", ""))


def build_ai_result_signature(
    *,
    query: str,
    settings: dict,
    retrieval_mode: str,
    context_source: str,
    use_current_context: bool,
) -> dict:
    """Return a stable signature for detecting stale generated AI results."""
    language = settings.get("language") or settings.get("answer_language") or "zh"
    source_mappings = list(settings.get("source_mappings") or [])
    return {
        "query": query,
        "language": language,
        "answer_language": language,
        "provider": settings.get("provider", "mock"),
        "top_k": int(settings.get("top_k", 0)),
        "ai_context_count": int(settings.get("ai_context_count", settings.get("top_k", 0)) or 0),
        "model": _effective_model_for_settings(settings),
        "retrieval_mode": retrieval_mode,
        "context_source": context_source,
        "use_current_context": bool(use_current_context),
        "source_mapping_citations": [mapping.get("citation", "") for mapping in source_mappings],
        "source_mappings": source_mappings,
    }


def attach_ai_result_signature(result: dict, signature: dict) -> dict:
    """Attach a signature and convenient metadata fields to a generated AI result."""
    metadata = dict(result.get("metadata") or {})
    metadata["result_signature"] = signature
    metadata["result_language"] = signature.get("answer_language") or signature.get("language")
    metadata["answer_language"] = signature.get("answer_language") or signature.get("language")
    metadata["query"] = signature.get("query")
    metadata["provider"] = signature.get("provider")
    metadata["top_k"] = signature.get("top_k")
    metadata["ai_context_count"] = signature.get("ai_context_count")
    metadata["model"] = signature.get("model")
    metadata["context_source"] = signature.get("context_source")
    if signature.get("source_mappings") and not metadata.get("source_mappings"):
        metadata["source_mappings"] = signature.get("source_mappings")
    result["metadata"] = metadata
    return result


def is_ai_result_stale(result_metadata: dict | None, current_signature: dict) -> bool:
    """Return True when generated result metadata no longer matches current settings."""
    if not result_metadata:
        return False
    return result_metadata.get("result_signature") != current_signature


def summarize_effective_ai_settings(settings: dict, labels: dict[str, str]) -> str:
    """Summarize the settings that will actually be used by an AI panel."""
    prefix = labels.get("current_effective_settings", "Current effective settings") if settings.get("panel_local_settings") else (
        labels.get("panel_override_summary", "Panel override is active")
        if settings.get("override_enabled")
        else labels.get("use_global_settings_summary", "Using global settings")
    )
    provider_label = labels.get("provider", "Provider")
    language_label = labels.get("answer_language", "Answer language")
    model_label = labels.get("model", "Model")
    model = _effective_model_for_settings(settings)
    model_part = f", {model_label}={model}" if model else ""
    language = settings.get("language") or settings.get("answer_language")
    if settings.get("language_choice") == "auto":
        language = labels.get("answer_language_auto_effective", "Auto (current: {language})").format(language=language)
    return (
        f"{prefix}: Top K={settings.get('top_k')}, "
        f"{provider_label}={settings.get('provider')}, "
        f"{language_label}={language}"
        f"{model_part}"
    )


def extract_paper_snippet_preview(item: dict) -> str:
    """Return the best available paper snippet without reading PDF content."""
    for chunk_key in ("used_chunks", "matched_chunks"):
        for chunk in item.get(chunk_key) or []:
            for key in ("snippet", "display_text", "text"):
                value = chunk.get(key)
                if value:
                    return str(value).strip()

    for key in ("snippet", "display_text", "text"):
        value = item.get(key)
        if value:
            return str(value).strip()

    metadata = item.get("metadata") or {}
    for key in ("snippet", "abstract", "summary", "display_text", "text"):
        value = metadata.get(key)
        if value:
            return str(value).strip()
    return ""


def build_paper_card_context(item: dict, labels: dict[str, str]) -> dict:
    """Normalize a search result/topic candidate for UI paper-card rendering."""
    matched_count = item.get("matched_chunk_count") or len(item.get("matched_chunks") or [])
    used_aliases = list(item.get("used_aliases") or [])
    return {
        "rank": item.get("rank", "-"),
        "title": item.get("title") or item.get("doc_id") or "Untitled",
        "year": item.get("year") or "",
        "advisor": item.get("advisor_name") or item.get("advisor") or "",
        "citation": item.get("citation") or "",
        "used_aliases": used_aliases,
        "used_aliases_label": labels.get("used_citation_aliases", "Used citation aliases"),
        "similarity_label": labels.get("similarity", "Similarity"),
        "similarity": f"{float(item.get('score', 0.0)):.4f}" if item.get("score") is not None else "",
        "matched_label": labels.get("used_chunks", labels.get("matched_paragraph_count", "Matched paragraphs"))
        if used_aliases
        else labels.get("matched_paragraph_count", "Matched paragraphs"),
        "matched_count": matched_count,
        "snippet": extract_paper_snippet_preview(item) or labels.get("no_snippet_available", "No snippet available."),
    }


def build_risk_explanation(labels: dict[str, str]) -> str:
    """Return the UI explanation for topic risk thresholds used by the current code."""
    return (
        f"{labels.get('risk_explanation', '')} "
        f"{labels.get('risk_thresholds', '')} "
        f"(medium >= {RISK_MEDIUM_THRESHOLD:.2f}, high >= {RISK_HIGH_THRESHOLD:.2f})"
    ).strip()


def _validate_workspace_path(path: Path) -> Path:
    resolved = path.resolve()
    try:
        resolved.relative_to(WORKSPACE_ROOT)
    except ValueError as exc:
        raise ValueError("Refusing to access files outside the project workspace") from exc

    if any(part.lower() in FORBIDDEN_PARTS for part in resolved.parts):
        raise ValueError("Refusing to access a forbidden private data directory")
    return resolved


def _display_path(path: Path) -> str:
    try:
        return path.resolve().relative_to(WORKSPACE_ROOT).as_posix()
    except ValueError:
        return path.name


def _display_internal_path(path: Path) -> str:
    """Avoid showing absolute internal PDF paths in user-facing UI state."""
    return path.name


def _file_mtime(path: Path) -> float:
    return path.stat().st_mtime if path.exists() else 0.0


@st.cache_resource(show_spinner=False)
def load_cached_index(index_path: str, index_mtime: float) -> TfidfRetriever:
    """Load a TF-IDF retriever, invalidating the cache when the index file changes."""
    del index_mtime
    return TfidfRetriever.load(Path(index_path))


@st.cache_data(show_spinner=False)
def load_cached_catalog(catalog_path: str, catalog_mtime: float) -> list[dict]:
    """Load catalog rows, invalidating the cache when the CSV changes."""
    del catalog_mtime
    return load_catalog(Path(catalog_path))


@st.cache_data(show_spinner=False)
def load_cached_documents(metadata_path: str, metadata_mtime: float) -> list[dict]:
    """Load document metadata JSONL, invalidating the cache when the file changes."""
    del metadata_mtime
    path = Path(metadata_path)
    if not path.exists():
        return []
    records: list[dict] = []
    with path.open("r", encoding="utf-8") as handle:
        for line in handle:
            stripped = line.strip()
            if stripped:
                records.append(json.loads(stripped))
    return records


@st.cache_data(show_spinner=False)
def load_cached_sample_names(samples_dir: str, samples_mtime: float) -> list[str]:
    """Load synthetic sample names, invalidating when the samples directory changes."""
    del samples_mtime
    path = Path(samples_dir)
    if not path.exists():
        return []
    return sorted(item.name for item in path.iterdir() if item.is_file() and item.suffix.lower() == ".md")


def _chunk_count_from_jsonl(chunks_path: Path) -> int:
    if not chunks_path.exists():
        return 0
    return len(load_chunks_jsonl(chunks_path))


def get_demo_asset_status(
    chunks_path: Path,
    metadata_path: Path,
    index_path: Path,
) -> dict:
    """Return cheap demo asset status without rebuilding or scanning raw documents."""
    safe_chunks_path = _validate_workspace_path(chunks_path)
    safe_metadata_path = _validate_workspace_path(metadata_path)
    safe_index_path = _validate_workspace_path(index_path)
    status = {
        "mode": "demo",
        "chunks_exists": safe_chunks_path.exists(),
        "index_exists": safe_index_path.exists(),
        "metadata_exists": safe_metadata_path.exists(),
        "chunk_count": _chunk_count_from_jsonl(safe_chunks_path),
        "index_path": _display_path(safe_index_path),
        "chunks_path": _display_path(safe_chunks_path),
        "metadata_path": _display_path(safe_metadata_path),
    }
    status.update(_snapshot_status_for_mode("demo"))
    return status


def get_internal_asset_status(
    catalog_path: Path,
    chunks_path: Path,
    index_path: Path,
) -> dict:
    """Return cheap internal asset status without syncing, ingesting, indexing, or scanning PDFs."""
    status = {
        "mode": "internal",
        "catalog_exists": catalog_path.exists(),
        "chunks_exists": chunks_path.exists(),
        "index_exists": index_path.exists(),
        "chunk_count": _chunk_count_from_jsonl(chunks_path) if chunks_path.exists() else 0,
        "catalog_count": len(load_cached_catalog(str(catalog_path), _file_mtime(catalog_path)))
        if catalog_path.exists()
        else 0,
        "index_path": _display_internal_path(index_path),
        "chunks_path": _display_internal_path(chunks_path),
        "catalog_path": _display_internal_path(catalog_path),
    }
    status.update(_snapshot_status_for_mode("internal"))
    return status


def rebuild_demo_assets(
    samples_dir: Path,
    chunks_path: Path,
    metadata_path: Path,
    index_path: Path,
    language: str = "ja",
) -> dict:
    """Rebuild synthetic demo assets from local sample files."""
    safe_samples_dir = _validate_workspace_path(samples_dir)
    safe_chunks_path = _validate_workspace_path(chunks_path)
    safe_metadata_path = _validate_workspace_path(metadata_path)
    safe_index_path = _validate_workspace_path(index_path)

    ingest_documents(
        input_dir=safe_samples_dir,
        chunks_output=safe_chunks_path,
        metadata_output=safe_metadata_path,
        input_type="markdown",
        language=language,
    )
    build_tfidf_index(
        chunks_path=safe_chunks_path,
        index_output=safe_index_path,
        language=language,
    )

    return get_demo_asset_status(
        chunks_path=safe_chunks_path,
        metadata_path=safe_metadata_path,
        index_path=safe_index_path,
    )


def ensure_demo_assets(
    samples_dir: Path,
    chunks_path: Path,
    metadata_path: Path,
    index_path: Path,
    language: str = "ja",
) -> dict:
    """Backward-compatible demo helper that rebuilds only when assets are missing."""
    safe_samples_dir = _validate_workspace_path(samples_dir)
    status = get_demo_asset_status(chunks_path=chunks_path, metadata_path=metadata_path, index_path=index_path)
    if not status["chunks_exists"] or not status["index_exists"]:
        return rebuild_demo_assets(
            samples_dir=safe_samples_dir,
            chunks_path=chunks_path,
            metadata_path=metadata_path,
            index_path=index_path,
            language=language,
        )
    return status


def rebuild_internal_assets(
    pdf_root: Path,
    catalog_path: Path,
    chunks_path: Path,
    index_path: Path,
    language: str = "ja",
) -> dict:
    """Explicitly rebuild internal catalog, chunks, and index from a configured PDF root."""
    if not pdf_root:
        raise ValueError("Internal mode requires LAB_PDF_ROOT")

    sync_catalog(pdf_root=pdf_root, catalog_path=catalog_path)
    ingest_documents(
        input_dir=pdf_root,
        chunks_output=chunks_path,
        metadata_output=chunks_path.with_name("documents.jsonl"),
        input_type="pdf",
        language=language,
        catalog_path=catalog_path,
    )
    build_tfidf_index(chunks_path=chunks_path, index_output=index_path, language=language)
    return get_internal_asset_status(catalog_path=catalog_path, chunks_path=chunks_path, index_path=index_path)


def ensure_internal_assets(
    pdf_root: Path,
    catalog_path: Path,
    chunks_path: Path,
    index_path: Path,
    language: str = "ja",
) -> dict:
    """Backward-compatible internal helper; explicit rebuild only when required by old callers."""
    status = get_internal_asset_status(catalog_path=catalog_path, chunks_path=chunks_path, index_path=index_path)
    if not status["catalog_exists"] or not status["chunks_exists"] or not status["index_exists"]:
        return rebuild_internal_assets(
            pdf_root=pdf_root,
            catalog_path=catalog_path,
            chunks_path=chunks_path,
            index_path=index_path,
            language=language,
        )
    return status


def load_internal_catalog(catalog_path: Path) -> list[dict]:
    """Load active internal catalog records for UI display."""
    records = load_cached_catalog(str(catalog_path), _file_mtime(catalog_path))
    return [record for record in records if record.get("status", "active") == "active"]


def _catalog_lookup(catalog_path: Path | None) -> dict[str, dict]:
    if catalog_path is None or not catalog_path.exists():
        return {}
    records = load_cached_catalog(str(catalog_path), _file_mtime(catalog_path))
    return {record["doc_id"]: record for record in records if record.get("status", "active") == "active"}


def _documents_lookup(metadata_path: Path | None) -> dict[str, dict]:
    if metadata_path is None or not metadata_path.exists():
        return {}
    records = load_cached_documents(str(metadata_path), _file_mtime(metadata_path))
    return {record["doc_id"]: record for record in records if record.get("doc_id")}


def resolve_doc_id_to_pdf(
    catalog_path: Path,
    doc_id: str,
    pdf_root: Path | None = None,
) -> Path:
    """Resolve an internal doc_id to a catalog PDF path."""
    record = _catalog_lookup(catalog_path).get(doc_id) or catalog_by_doc_id(catalog_path).get(doc_id)
    if not record:
        raise ValueError(f"Unknown internal doc_id: {doc_id}")
    pdf_path = Path(record["pdf_path"]).resolve()
    if pdf_root is not None:
        try:
            pdf_path.relative_to(pdf_root.resolve())
        except ValueError as exc:
            raise ValueError("Resolved PDF is outside the configured internal PDF root") from exc
    return pdf_path


def get_pdf_download_bytes(
    catalog_path: Path,
    doc_id: str,
    pdf_root: Path | None = None,
) -> bytes:
    """Return bytes for a catalog-validated internal PDF."""
    pdf_path = resolve_doc_id_to_pdf(catalog_path=catalog_path, doc_id=doc_id, pdf_root=pdf_root)
    return read_pdf_bytes(pdf_path=pdf_path, pdf_root=pdf_root)


def build_pdf_action_metadata(
    catalog_path: Path,
    doc_id: str,
    pdf_root: Path | None = None,
) -> dict:
    """Return validated PDF action metadata without exposing raw paths as labels."""
    pdf_path = resolve_doc_id_to_pdf(catalog_path=catalog_path, doc_id=doc_id, pdf_root=pdf_root)
    return {
        "doc_id": doc_id,
        "file_name": f"{doc_id}.pdf",
        "pdf_path": pdf_path,
        "can_open": True,
        "can_download": True,
    }


def persist_search_result(state: dict, query: str, result: dict) -> None:
    """Persist search UI state across Streamlit reruns."""
    state["last_search_query"] = query
    state["last_search_results"] = result


def persist_topic_result(state: dict, topic: str, result: dict) -> None:
    """Persist topic UI state across Streamlit reruns."""
    state["last_topic"] = topic
    state["last_topic_analysis"] = result
    state["last_topic_report"] = result.get("report_markdown", "")


def make_pdf_preview_state_key(key_prefix: str, item: dict, rank: int) -> str:
    """Build a stable per-paper PDF preview state key."""
    identifier = (
        item.get("citation")
        or item.get("chunk_id")
        or item.get("doc_id")
        or f"{item.get('title', '')}#{rank}"
    )
    digest = hashlib.sha1(str(identifier).encode("utf-8")).hexdigest()[:16]
    return f"{key_prefix}_preview_{digest}"


def toggle_pdf_preview_state(state: dict, state_key: str) -> None:
    """Toggle exactly one PDF preview state flag."""
    state[state_key] = not bool(state.get(state_key, False))


def clear_pdf_preview_state_for_prefix(state: dict, prefix: str) -> None:
    """Clear PDF preview state keys for a single result group prefix."""
    for key in list(state.keys()):
        if str(key).startswith(prefix):
            state.pop(key, None)


def build_pdf_preview_results_signature(results: list[dict]) -> tuple[str, ...]:
    """Return a stable signature for the currently visible paper result set."""
    signature: list[str] = []
    for index, item in enumerate(results or [], start=1):
        signature.append(
            str(
                item.get("citation")
                or item.get("chunk_id")
                or item.get("doc_id")
                or f"{item.get('title', '')}#{item.get('rank', index)}"
            )
        )
    return tuple(signature)


def maybe_clear_pdf_preview_state_on_results_change(
    state: dict,
    prefix: str,
    current_signature: tuple,
    signature_key: str,
) -> None:
    """Clear stale preview flags only when the visible result set changes."""
    previous_signature = state.get(signature_key)
    if previous_signature is None:
        state[signature_key] = current_signature
        return
    if tuple(previous_signature) != tuple(current_signature):
        clear_pdf_preview_state_for_prefix(state, prefix)
        state[signature_key] = current_signature


def list_demo_samples(samples_dir: Path) -> list[str]:
    """Return sorted synthetic sample filenames from a safe local directory."""
    safe_samples_dir = _validate_workspace_path(samples_dir)
    if not safe_samples_dir.exists():
        return []
    return load_cached_sample_names(str(safe_samples_dir), _file_mtime(safe_samples_dir))


def _format_search_result(result: SearchResult, catalog_record: dict | None = None, document_record: dict | None = None) -> dict:
    metadata = dict(result.metadata)
    if document_record:
        metadata.update({key: value for key, value in document_record.items() if value})
    if catalog_record:
        metadata.update({key: value for key, value in catalog_record.items() if value})
    return {
        "rank": result.rank,
        "score": round(result.score, 4),
        "title": metadata.get("title") or result.title,
        "citation": result.citation,
        "snippet": result.text[:160].replace("\n", " "),
        "chunk_id": result.chunk_id,
        "doc_id": result.doc_id,
        "author_name": metadata.get("author_name", ""),
        "advisor_name": metadata.get("advisor_name", ""),
        "year": metadata.get("year", ""),
        "pdf_path": metadata.get("pdf_path", ""),
        "original_filename": metadata.get("original_filename", ""),
        "source_type": metadata.get("source_type", ""),
    }


def dedupe_results_by_doc_id(results: list[dict], top_k: int) -> list[dict]:
    """Collapse chunk-level hits into document-level search results."""
    best_by_doc_id: dict[str, dict] = {}
    matched_chunks_by_doc_id: dict[str, list[dict]] = {}

    for result in results:
        doc_id = result.get("doc_id", "")
        if not doc_id:
            continue

        chunk_summary = {
            "rank": result.get("rank"),
            "score": result.get("score", 0.0),
            "citation": result.get("citation", ""),
            "chunk_id": result.get("chunk_id", ""),
            "snippet": result.get("snippet", ""),
        }
        matched_chunks_by_doc_id.setdefault(doc_id, []).append(chunk_summary)

        current_best = best_by_doc_id.get(doc_id)
        if current_best is None or float(result.get("score", 0.0)) > float(current_best.get("score", 0.0)):
            best_by_doc_id[doc_id] = dict(result)

    deduped = sorted(best_by_doc_id.values(), key=lambda item: float(item.get("score", 0.0)), reverse=True)
    deduped = deduped[: max(top_k, 0)]
    for index, result in enumerate(deduped, start=1):
        doc_id = result["doc_id"]
        matched_chunks = sorted(
            matched_chunks_by_doc_id.get(doc_id, []),
            key=lambda item: float(item.get("score", 0.0)),
            reverse=True,
        )
        result["rank"] = index
        result["matched_chunk_count"] = len(matched_chunks)
        result["matched_chunks"] = matched_chunks
    return deduped


def _search_cached_index(
    index_path: Path,
    query: str,
    top_k: int,
    catalog_path: Path | None = None,
    metadata_path: Path | None = None,
) -> tuple[list[dict], float]:
    start = time.perf_counter()
    retriever = load_cached_index(str(index_path), _file_mtime(index_path))
    catalog = _catalog_lookup(catalog_path)
    documents = _documents_lookup(metadata_path)
    candidate_k = max(top_k * 5, top_k)
    raw_results = retriever.search(query=query, top_k=candidate_k)
    results = [
        _format_search_result(
            result,
            catalog_record=catalog.get(result.doc_id),
            document_record=documents.get(result.doc_id),
        )
        for result in raw_results
    ]
    return dedupe_results_by_doc_id(results, top_k=top_k), time.perf_counter() - start


def run_search(
    index_path: Path,
    query: str,
    top_k: int = 5,
    kb_mode: str = "demo",
    catalog_path: Path | None = None,
    metadata_path: Path | None = None,
) -> dict:
    """Run local search and normalize the result for Streamlit rendering."""
    if not query or not query.strip():
        return {"ok": False, "errors": ["Query must not be empty."], "warnings": [], "query": query, "results": []}

    pii_findings = scan_pii(query)
    if pii_findings and kb_mode != "internal":
        return {
            "ok": False,
            "errors": ["PII detected in query. Please remove personal or sensitive information before searching."],
            "warnings": [],
            "query": query,
            "results": [],
        }

    safe_index_path = _validate_workspace_path(index_path) if kb_mode == "demo" else index_path
    try:
        results, elapsed = _search_cached_index(
            index_path=safe_index_path,
            query=query,
            top_k=top_k,
            catalog_path=catalog_path if kb_mode == "internal" else None,
            metadata_path=metadata_path,
        )
    except Exception as exc:
        return {"ok": False, "errors": [str(exc)], "warnings": [], "query": query, "results": []}
    return {
        "ok": True,
        "errors": [],
        "warnings": [],
        "query": query,
        "results": results,
        "timing": {"search_seconds": round(elapsed, 4)},
    }


def _compare_topic_from_results(topic: str, results: list[dict], *, language: str = "ja") -> ToolResult:
    top_score = float(results[0]["score"]) if results else 0.0
    risk_level = risk_level_from_score(top_score)
    return ToolResult(
        tool_name="compare_topic",
        ok=True,
        data={
            "topic": topic,
            "risk_level": risk_level,
            "risk_score": round(top_score, 4),
            "top_similarity_score": round(top_score, 4),
            "similar_count": len(results),
            "citations": [result["citation"] for result in results],
            "recommendations": _build_recommendations(risk_level, language=language),
            "references": results,
            "note": "This is only a topic similarity / overlap signal, not plagiarism detection.",
        },
    )


def run_topic_analysis(
    index_path: Path,
    topic: str,
    top_k: int = 5,
    language: str = "ja",
    kb_mode: str = "demo",
    catalog_path: Path | None = None,
    metadata_path: Path | None = None,
) -> dict:
    """Run deterministic topic analysis and local MockLLM report generation."""
    start = time.perf_counter()
    search_result = run_search(
        index_path=index_path,
        query=topic,
        top_k=top_k,
        kb_mode=kb_mode,
        catalog_path=catalog_path,
        metadata_path=metadata_path,
    )
    if not search_result["ok"]:
        return {
            "ok": False,
            "errors": search_result["errors"],
            "warnings": search_result["warnings"],
            "risk_level": "",
            "risk_score": 0.0,
            "citations": [],
            "report_markdown": "",
            "result_count": 0,
        }

    topic_result = _compare_topic_from_results(topic, search_result["results"], language=language)
    report_markdown = MockLLM().generate_topic_report(
        topic=topic,
        topic_analysis=topic_result.data,
        search_results=search_result["results"],
        language=language,
    )

    return {
        "ok": True,
        "errors": [],
        "warnings": topic_result.warnings,
        "risk_level": topic_result.data["risk_level"],
        "risk_score": topic_result.data["risk_score"],
        "citations": topic_result.data["citations"],
        "references": topic_result.data.get("references", []),
        "report_markdown": report_markdown,
        "result_count": len(search_result["results"]),
        "note": topic_result.data.get("note", ""),
        "timing": {
            "topic_seconds": round(time.perf_counter() - start, 4),
            **search_result.get("timing", {}),
        },
    }


def run_structure_check(
    sample_path: Path,
    language: str = "ja",
) -> dict:
    """Run local structure analysis on a safe synthetic sample file."""
    safe_sample_path = _validate_workspace_path(sample_path)
    result = analyze_structure_file(path=safe_sample_path, language=language)
    return {
        "ok": result.ok,
        "errors": result.errors,
        "warnings": result.warnings,
        "score": result.data.get("score", 0.0),
        "language": result.data.get("language", language),
        "present_sections": result.data.get("present_sections", []),
        "missing_sections": result.data.get("missing_sections", []),
        "suggestions": result.data.get("suggestions", []),
        "sample_name": safe_sample_path.name,
    }


def build_rag_contexts_from_search_results(
    results: list[dict],
    *,
    top_k: int,
    source_type: str = "current_search_results",
) -> list[dict]:
    contexts = []
    mappings = build_ai_source_mappings(results or [], source_type=source_type, limit=top_k)
    for index, item in enumerate((results or [])[: max(top_k, 0)]):
        snippet = extract_paper_snippet_preview(item)
        metadata = {key: value for key, value in item.items() if key not in {"snippet", "matched_chunks"}}
        if index < len(mappings):
            metadata["source_mapping"] = mappings[index]
        metadata["source_type"] = source_type
        contexts.append(
            {
                "title": item.get("title", ""),
                "citation": item.get("citation", ""),
                "snippet": snippet,
                "doc_id": item.get("doc_id", ""),
                "chunk_id": item.get("chunk_id", ""),
                "metadata": metadata,
            }
        )
    return contexts


def build_rag_contexts_from_topic_candidates(candidates: list[dict], *, top_k: int) -> list[dict]:
    return build_rag_contexts_from_search_results(
        candidates or [],
        top_k=top_k,
        source_type="current_topic_candidates",
    )


def run_local_ai_answer(
    *,
    query: str,
    retrieval_mode: str,
    llm_provider: str,
    language: str,
    top_k: int,
    tfidf_index_path: Path,
    vector_persist_dir: Path | None,
    vector_collection: str,
    embedding_provider: str,
    ollama_base_url: str = OLLAMA_BASE_URL_EXAMPLE,
    ollama_model: str = "",
    ollama_temperature: float = 0.2,
    ollama_num_ctx: int = 4096,
    ollama_num_predict: int | None = None,
    api_base_url: str | None = None,
    api_model: str | None = None,
    api_key: str | None = None,
    api_timeout_seconds: int = 90,
    api_temperature: float = 0.2,
    api_max_tokens: int = 1200,
    max_language_retries: int = 2,
    current_search_results: list[dict] | None = None,
    use_current_search_results: bool = True,
    include_low_similarity_contexts: bool = False,
) -> dict:
    warnings: list[str] = []
    provided_contexts = None
    visible_count = len(current_search_results or [])
    eligible_results, omitted_contexts = filter_ai_eligible_contexts(
        current_search_results,
        include_low_similarity_contexts=include_low_similarity_contexts,
    )
    omitted_reasons = [item["reason"] for item in omitted_contexts]
    requested_top_k = int(top_k)
    ai_context_count = requested_top_k
    source_mappings: list[dict] = []
    context_source = "retrieval"
    retrieval_metadata: dict = {}
    if use_current_search_results and eligible_results:
        ai_context_count, clamped = clamp_ai_context_count(
            requested_top_k,
            visible_count=len(eligible_results),
        )
        if clamped:
            warnings.append("ai_context_count_clamped_to_eligible_results")
        if omitted_contexts:
            warnings.append("low_quality_contexts_omitted")
        provided_contexts = build_rag_contexts_from_search_results(
            eligible_results,
            top_k=ai_context_count,
            source_type="current_search_results",
        )
        source_mappings = build_ai_source_mappings(
            eligible_results,
            source_type="current_search_results",
            limit=ai_context_count,
        )
        context_source = "current_search_results"
        warnings.append("using_current_search_results")
        if len(eligible_results) > ai_context_count:
            warnings.append("current_search_results_truncated_to_top_k")
    elif use_current_search_results:
        warnings.append("no_current_search_results_choose_retrieval")
        if omitted_contexts:
            warnings.append("low_quality_contexts_omitted")
        return {
            "ok": False,
            "answer_markdown": "",
            "citations": [],
            "retrieved_count": 0,
            "warnings": warnings,
            "errors": ["no_current_search_results_choose_retrieval"],
            "metadata": {
                "context_source": "current_search_results",
                "ai_context_count": 0,
                "visible_result_count": visible_count,
                "eligible_context_count": len(eligible_results),
                "omitted_context_count": len(omitted_contexts),
                "omitted_context_reasons": omitted_reasons,
                "include_low_similarity_contexts": include_low_similarity_contexts,
                "source_mappings": [],
            },
            "provider": llm_provider,
            "model": "",
            "retrieval_mode": retrieval_mode,
        }
    else:
        retrieval_payload = retrieve_ai_paper_contexts(
            query=query,
            retrieval_mode=retrieval_mode,
            target_paper_count=requested_top_k,
            tfidf_index_path=tfidf_index_path,
            vector_persist_dir=vector_persist_dir,
            vector_collection=vector_collection,
            embedding_provider=embedding_provider,
            provider=llm_provider,
        )
        warnings.extend(retrieval_payload["warnings"])
        provided_contexts = retrieval_payload["contexts"]
        source_mappings = retrieval_payload["source_mappings"]
        ai_context_count = len(provided_contexts)
        retrieval_mode = retrieval_payload["effective_retrieval_mode"]
        retrieval_metadata = {
            "retrieval_target_paper_count": retrieval_payload["retrieval_target_paper_count"],
            "retrieval_raw_chunk_count": retrieval_payload["retrieval_raw_chunk_count"],
            "retrieval_raw_chunk_top_k": retrieval_payload["retrieval_raw_chunk_top_k"],
            "retrieval_deduped_paper_count": retrieval_payload["retrieval_deduped_paper_count"],
            "ai_retrieval_requested_top_k": retrieval_payload.get("ai_retrieval_requested_top_k", retrieval_payload["retrieval_target_paper_count"]),
            "ai_retrieval_actual_source_count": retrieval_payload.get("ai_retrieval_actual_source_count", len(provided_contexts)),
            "ai_retrieval_unique_paper_count": retrieval_payload.get("ai_retrieval_unique_paper_count", retrieval_payload["retrieval_deduped_paper_count"]),
            "dedupe_strategy": retrieval_payload["dedupe_strategy"],
            "max_chunks_per_paper": retrieval_payload.get("max_chunks_per_paper"),
            "omitted_chunks_per_paper": retrieval_payload.get("omitted_chunks_per_paper", {}),
            "context_budget_chars": retrieval_payload.get("context_budget_chars"),
            "context_chars_before_trim": retrieval_payload.get("context_chars_before_trim"),
            "context_chars_after_trim": retrieval_payload.get("context_chars_after_trim"),
            "context_budget_applied": retrieval_payload.get("context_budget_applied", False),
        }
        if not provided_contexts:
            return {
                "ok": False,
                "answer_markdown": "",
                "citations": [],
                "retrieved_count": 0,
                "warnings": warnings,
                "errors": ["no_ai_retrieval_sources"],
                "metadata": {
                    "context_source": "retrieval",
                    "ai_context_count": 0,
                    "visible_result_count": visible_count,
                    "source_mappings": [],
                    **retrieval_metadata,
                },
                "provider": llm_provider,
                "model": "",
                "retrieval_mode": retrieval_mode,
            }
    result = generate_rag_answer(
        query=query,
        retrieval_mode=retrieval_mode,
        llm_provider_name=llm_provider,
        language=language,
        top_k=ai_context_count,
        tfidf_index_path=tfidf_index_path,
        vector_persist_dir=vector_persist_dir,
        vector_collection=vector_collection,
        embedding_provider_name=embedding_provider,
        ollama_base_url=ollama_base_url,
        ollama_model=ollama_model,
        ollama_temperature=ollama_temperature,
        ollama_num_ctx=ollama_num_ctx,
        api_base_url=api_base_url,
        api_model=api_model,
        api_key=api_key,
        api_timeout_seconds=api_timeout_seconds,
        api_temperature=api_temperature,
        api_max_tokens=api_max_tokens,
        provided_contexts=provided_contexts,
        context_source=context_source,
        retry_missing_citations=True,
        retry_language_mismatch=True,
        max_language_retries=max_language_retries,
    )
    result_dict = _rag_result_to_dict(result, extra_warnings=warnings)
    metadata = dict(result_dict.get("metadata") or {})
    metadata["context_source"] = context_source
    metadata["ai_context_count"] = ai_context_count
    metadata["visible_result_count"] = visible_count
    metadata["eligible_context_count"] = len(eligible_results) if use_current_search_results else ai_context_count
    metadata["omitted_context_count"] = len(omitted_contexts) if use_current_search_results else 0
    metadata["omitted_context_reasons"] = omitted_reasons if use_current_search_results else []
    metadata["include_low_similarity_contexts"] = include_low_similarity_contexts
    metadata["source_mappings"] = metadata.get("source_mappings") or source_mappings
    metadata.update(retrieval_metadata)
    result_dict["metadata"] = metadata
    return result_dict


def run_topic_ai_assist(
    *,
    topic_query: str,
    topic_candidates: list[dict] | None,
    retrieval_mode: str,
    llm_provider: str,
    language: str,
    top_k: int,
    tfidf_index_path: Path,
    vector_persist_dir: Path | None,
    vector_collection: str,
    embedding_provider: str,
    ollama_base_url: str = OLLAMA_BASE_URL_EXAMPLE,
    ollama_model: str = "",
    ollama_temperature: float = 0.2,
    ollama_num_ctx: int = 4096,
    ollama_num_predict: int | None = None,
    api_base_url: str | None = None,
    api_model: str | None = None,
    api_key: str | None = None,
    api_timeout_seconds: int = 90,
    api_temperature: float = 0.2,
    api_max_tokens: int = 1200,
    max_language_retries: int = 2,
    use_topic_candidates: bool = True,
    include_low_similarity_contexts: bool = False,
) -> dict:
    warnings: list[str] = []
    provided_contexts = None
    visible_count = len(topic_candidates or [])
    eligible_candidates, omitted_contexts = filter_ai_eligible_contexts(
        topic_candidates,
        include_low_similarity_contexts=include_low_similarity_contexts,
    )
    omitted_reasons = [item["reason"] for item in omitted_contexts]
    requested_top_k = int(top_k)
    ai_context_count = requested_top_k
    source_mappings: list[dict] = []
    context_source = "retrieval"
    retrieval_metadata: dict = {}
    if use_topic_candidates and eligible_candidates:
        ai_context_count, clamped = clamp_ai_context_count(
            requested_top_k,
            visible_count=len(eligible_candidates),
        )
        if clamped:
            warnings.append("ai_context_count_clamped_to_eligible_results")
        if omitted_contexts:
            warnings.append("low_quality_contexts_omitted")
        provided_contexts = build_rag_contexts_from_topic_candidates(eligible_candidates, top_k=ai_context_count)
        source_mappings = build_ai_source_mappings(
            eligible_candidates,
            source_type="current_topic_candidates",
            limit=ai_context_count,
        )
        context_source = "current_topic_candidates"
        warnings.append("using_topic_candidates")
        if len(eligible_candidates) > ai_context_count:
            warnings.append("current_search_results_truncated_to_top_k")
    elif use_topic_candidates:
        warnings.append("no_topic_candidates_choose_retrieval")
        if omitted_contexts:
            warnings.append("low_quality_contexts_omitted")
        return {
            "ok": False,
            "answer_markdown": "",
            "citations": [],
            "retrieved_count": 0,
            "warnings": warnings,
            "errors": ["no_topic_candidates_choose_retrieval"],
            "metadata": {
                "context_source": "current_topic_candidates",
                "ai_context_count": 0,
                "visible_result_count": visible_count,
                "eligible_context_count": len(eligible_candidates),
                "omitted_context_count": len(omitted_contexts),
                "omitted_context_reasons": omitted_reasons,
                "include_low_similarity_contexts": include_low_similarity_contexts,
                "source_mappings": [],
            },
            "provider": llm_provider,
            "model": "",
            "retrieval_mode": retrieval_mode,
        }
    else:
        retrieval_payload = retrieve_ai_paper_contexts(
            query=topic_query,
            retrieval_mode=retrieval_mode,
            target_paper_count=requested_top_k,
            tfidf_index_path=tfidf_index_path,
            vector_persist_dir=vector_persist_dir,
            vector_collection=vector_collection,
            embedding_provider=embedding_provider,
            provider=llm_provider,
        )
        warnings.extend(retrieval_payload["warnings"])
        provided_contexts = retrieval_payload["contexts"]
        source_mappings = retrieval_payload["source_mappings"]
        ai_context_count = len(provided_contexts)
        retrieval_mode = retrieval_payload["effective_retrieval_mode"]
        retrieval_metadata = {
            "retrieval_target_paper_count": retrieval_payload["retrieval_target_paper_count"],
            "retrieval_raw_chunk_count": retrieval_payload["retrieval_raw_chunk_count"],
            "retrieval_raw_chunk_top_k": retrieval_payload["retrieval_raw_chunk_top_k"],
            "retrieval_deduped_paper_count": retrieval_payload["retrieval_deduped_paper_count"],
            "ai_retrieval_requested_top_k": retrieval_payload.get("ai_retrieval_requested_top_k", retrieval_payload["retrieval_target_paper_count"]),
            "ai_retrieval_actual_source_count": retrieval_payload.get("ai_retrieval_actual_source_count", len(provided_contexts)),
            "ai_retrieval_unique_paper_count": retrieval_payload.get("ai_retrieval_unique_paper_count", retrieval_payload["retrieval_deduped_paper_count"]),
            "dedupe_strategy": retrieval_payload["dedupe_strategy"],
            "max_chunks_per_paper": retrieval_payload.get("max_chunks_per_paper"),
            "omitted_chunks_per_paper": retrieval_payload.get("omitted_chunks_per_paper", {}),
            "context_budget_chars": retrieval_payload.get("context_budget_chars"),
            "context_chars_before_trim": retrieval_payload.get("context_chars_before_trim"),
            "context_chars_after_trim": retrieval_payload.get("context_chars_after_trim"),
            "context_budget_applied": retrieval_payload.get("context_budget_applied", False),
        }
        if not provided_contexts:
            return {
                "ok": False,
                "answer_markdown": "",
                "citations": [],
                "retrieved_count": 0,
                "warnings": warnings,
                "errors": ["no_ai_retrieval_sources"],
                "metadata": {
                    "context_source": "retrieval",
                    "ai_context_count": 0,
                    "visible_result_count": visible_count,
                    "source_mappings": [],
                    **retrieval_metadata,
                },
                "provider": llm_provider,
                "model": "",
                "retrieval_mode": retrieval_mode,
            }
    query = (
        "Please provide topic advice, feasibility, risks, and recommended references based on this research direction: "
        + topic_query
    )
    result = generate_rag_answer(
        query=query,
        retrieval_mode=retrieval_mode,
        llm_provider_name=llm_provider,
        language=language,
        top_k=ai_context_count,
        tfidf_index_path=tfidf_index_path,
        vector_persist_dir=vector_persist_dir,
        vector_collection=vector_collection,
        embedding_provider_name=embedding_provider,
        ollama_base_url=ollama_base_url,
        ollama_model=ollama_model,
        ollama_temperature=ollama_temperature,
        ollama_num_ctx=ollama_num_ctx,
        api_base_url=api_base_url,
        api_model=api_model,
        api_key=api_key,
        api_timeout_seconds=api_timeout_seconds,
        api_temperature=api_temperature,
        api_max_tokens=api_max_tokens,
        provided_contexts=provided_contexts,
        context_source=context_source,
        retry_missing_citations=True,
        retry_language_mismatch=True,
        max_language_retries=max_language_retries,
    )
    result_dict = _rag_result_to_dict(result, extra_warnings=warnings)
    metadata = dict(result_dict.get("metadata") or {})
    metadata["context_source"] = context_source
    metadata["ai_context_count"] = ai_context_count
    metadata["visible_result_count"] = visible_count
    metadata["eligible_context_count"] = len(eligible_candidates) if use_topic_candidates else ai_context_count
    metadata["omitted_context_count"] = len(omitted_contexts) if use_topic_candidates else 0
    metadata["omitted_context_reasons"] = omitted_reasons if use_topic_candidates else []
    metadata["include_low_similarity_contexts"] = include_low_similarity_contexts
    metadata["source_mappings"] = metadata.get("source_mappings") or source_mappings
    metadata.update(retrieval_metadata)
    result_dict["metadata"] = metadata
    return result_dict


def classify_ai_warnings(warnings: list[str]) -> dict:
    important = []
    hidden = []
    for warning in warnings or []:
        if warning in ROUTINE_AI_WARNINGS:
            hidden.append(warning)
        else:
            important.append(warning)
    return {"important": important, "hidden": hidden}


def _rag_result_to_dict(result, *, extra_warnings: list[str] | None = None) -> dict:
    warnings = list(extra_warnings or []) + list(result.warnings)
    return {
        "ok": result.ok,
        "answer_markdown": result.answer_markdown,
        "citations": result.citations,
        "retrieved_count": result.retrieved_count,
        "warnings": warnings,
        "errors": result.errors,
        "metadata": result.metadata,
        "provider": result.llm_provider,
        "model": result.model,
        "retrieval_mode": result.retrieval_mode,
    }


def _snapshot_status_for_mode(mode: str) -> dict:
    manifest_path = resolve_snapshot_manifest_path(mode)
    manifest = load_kb_snapshot_manifest(manifest_path)
    history_path = resolve_snapshot_history_path(manifest_path, mode=mode)
    record_dir = resolve_snapshot_record_dir(mode, manifest_path)
    history = load_snapshot_history(history_path)
    records = load_snapshot_records(record_dir)
    status = {
        "snapshot_available": manifest is not None,
        "snapshot_manifest_path": _display_snapshot_path(manifest_path, mode=mode) if manifest_path else "",
        "snapshot_history_path": _display_snapshot_path(history_path, mode=mode) if history_path else "",
        "snapshot_history_count": len(history),
        "snapshot_history": history,
        "snapshot_record_dir": _display_snapshot_path(record_dir, mode=mode) if record_dir else "",
        "snapshot_records_count": len(records),
        "snapshot_records": records,
    }
    if manifest:
        status.update(
            {
                "snapshot_id": manifest.snapshot_id,
                "snapshot_kind": manifest.snapshot_kind,
                "snapshot_created_at": manifest.created_at,
                "snapshot_document_count": manifest.document_count,
                "snapshot_chunk_count": manifest.chunk_count,
                "snapshot_embedding_provider": manifest.embedding_provider,
                "snapshot_git_branch": manifest.git_branch,
                "snapshot_git_commit": manifest.git_commit,
            }
        )
    return status


def _display_snapshot_path(path: Path | None, *, mode: str) -> str:
    if path is None:
        return ""
    return _display_path(path) if mode == "demo" else path.name
