"""Streamlit entry point for ThesisAgent."""

from __future__ import annotations

import importlib.util
import os
import re
from pathlib import Path

import streamlit as st
import streamlit.components.v1 as components

from thesis_agent import __version__
from thesis_agent.config import get_app_config
from thesis_agent.ui.i18n import get_ui_labels
from thesis_agent.ui.pdf_actions import open_pdf, pdf_bytes_to_data_uri, resolve_pdf_preview_payload
from thesis_agent.ui.services import (
    attach_ai_result_signature,
    build_paper_card_context,
    build_ai_result_signature,
    build_ai_source_mappings,
    build_ai_sources_display_payload,
    build_pdf_preview_results_signature,
    build_global_ai_settings,
    build_pdf_action_metadata,
    build_risk_explanation,
    classify_ai_warnings,
    enrich_ai_retrieved_sources_with_catalog,
    filter_ai_eligible_contexts,
    clamp_ai_retrieval_top_k_for_provider,
    get_ai_retrieval_top_k_limit,
    maybe_replace_timeout_errors,
    maybe_clear_pdf_preview_state_on_results_change,
    extract_paper_snippet_preview,
    get_demo_asset_status,
    get_internal_asset_status,
    get_runtime_llm_provider_choices,
    get_pdf_download_bytes,
    is_ai_result_stale,
    list_demo_samples,
    make_pdf_preview_state_key,
    max_current_context_count,
    merge_ai_panel_settings,
    normalize_runtime_provider,
    persist_search_result,
    persist_topic_result,
    resolve_internal_chunks_path,
    resolve_internal_tfidf_index_path,
    resolve_doc_id_to_pdf,
    run_local_ai_answer,
    run_search,
    run_structure_check,
    run_topic_ai_assist,
    run_topic_analysis,
    summarize_effective_ai_settings,
    toggle_pdf_preview_state,
)


SAMPLES_DIR = Path("data/samples")
CHUNKS_PATH = Path("data/processed/chunks.jsonl")
METADATA_PATH = Path("data/metadata/documents.jsonl")
INDEX_PATH = Path("data/index/tfidf_index.pkl")
RAG_INDEX_PATH = Path("data/index/structured_tfidf_index.pkl")
VECTOR_PATH = Path("data/vector/chroma")
VECTOR_COLLECTION = "thesis_agent_demo"
LOCAL_AI_LLM_PROVIDER_OPTIONS = get_runtime_llm_provider_choices()
LANGUAGE_OPTIONS = ("auto", "zh", "ja", "en")
CONCRETE_LANGUAGE_OPTIONS = ("zh", "ja", "en")
DEVELOPMENT_STAGE = "Release 0.1.0"
DEPLOY_HIDE_CSS = """
<style>
/* Hide Streamlit top-right chrome for the local app. */
[data-testid="stDeployButton"],
[data-testid="stAppDeployButton"],
[data-testid="stStatusWidget"],
[data-testid="stToolbar"],
[data-testid="stToolbarActions"],
[data-testid="stHeaderActionElements"],
button[aria-label="Deploy"] {
    display: none !important;
}
</style>
"""


def _ui_text(language: str) -> dict[str, str]:
    labels = dict(get_ui_labels(language))
    labels.setdefault("app_title", "ThesisAgent")
    labels.setdefault("language", "UI Language")
    return labels


def _label(labels: dict[str, str], key: str, fallback: str) -> str:
    return labels.get(key, fallback)


def _resolve_ui_language(selected_language: str, fallback_language: str = "zh") -> str:
    if selected_language in CONCRETE_LANGUAGE_OPTIONS:
        return selected_language
    return fallback_language if fallback_language in CONCRETE_LANGUAGE_OPTIONS else "zh"


def _resolve_answer_language(selected_language: str, ui_language: str) -> str:
    if selected_language in CONCRETE_LANGUAGE_OPTIONS:
        return selected_language
    return ui_language if ui_language in CONCRETE_LANGUAGE_OPTIONS else "zh"


def _language_label(option: str, labels: dict[str, str]) -> str:
    if option == "auto":
        return _label(labels, "auto", "Auto")
    return option


def _sync_followup_question_default(state: dict, *, question_key: str, source_value: str, marker_key: str) -> None:
    """Auto-fill a follow-up question until the user edits it."""
    previous_source = state.get(marker_key, "")
    current_question = state.get(question_key, "")
    if question_key not in state or current_question == previous_source:
        state[question_key] = source_value
    state[marker_key] = source_value


def _base_ai_settings(defaults: dict) -> dict:
    return build_global_ai_settings(defaults)


def _merge_panel_ai_settings(defaults: dict, override_enabled: bool, overrides: dict | None = None) -> dict:
    return merge_ai_panel_settings(_base_ai_settings(defaults), overrides or {}, override_enabled)


def _settings_summary(labels: dict[str, str], settings: dict) -> str:
    return summarize_effective_ai_settings(settings, labels)


def _result_signature(
    *,
    query: str,
    settings: dict,
    retrieval_mode: str,
    context_source: str,
    use_current_context: bool,
) -> dict:
    return build_ai_result_signature(
        query=query,
        settings=settings,
        retrieval_mode=retrieval_mode,
        context_source=context_source,
        use_current_context=use_current_context,
    )


def _attach_result_signature(result: dict, signature: dict) -> dict:
    return attach_ai_result_signature(result, signature)


def _is_result_stale(result: dict | None, expected_signature: dict) -> bool:
    if not result:
        return False
    return is_ai_result_stale(result.get("metadata") or {}, expected_signature)


def _safe_pdf_filename(item: dict) -> str:
    raw_name = item.get("title") or item.get("original_filename") or item.get("doc_id") or "thesis"
    stem = Path(str(raw_name)).stem
    safe_stem = re.sub(r'[\\/:*?"<>|]+', "_", stem).strip(" ._") or str(item.get("doc_id") or "thesis")
    return f"{safe_stem}.pdf"


def _pdf_preview_availability(*, st_module=st, find_spec=importlib.util.find_spec) -> dict[str, str | bool]:
    """Return whether the active Streamlit runtime can render the PDF preview."""
    has_st_pdf = callable(getattr(st_module, "pdf", None))
    has_streamlit_pdf = find_spec("streamlit_pdf") is not None
    if has_st_pdf and has_streamlit_pdf:
        return {"available": True, "reason": ""}
    if not has_streamlit_pdf:
        return {"available": False, "reason": "dependency_missing"}
    return {"available": False, "reason": "st_pdf_missing"}


def _render_pdf_iframe_fallback(pdf_bytes: bytes, *, height: int = 650) -> None:
    """Render a PDF data URI iframe fallback without exposing local file paths."""
    data_uri = pdf_bytes_to_data_uri(pdf_bytes)
    components.html(
        (
            f'<iframe title="PDF preview" src="{data_uri}" '
            f'width="100%" height="{height}" style="border: 0;"></iframe>'
        ),
        height=height + 20,
    )


def _render_pdf_preview_bytes(pdf_bytes: bytes, labels: dict[str, str], *, height: int = 650) -> None:
    """Render a PDF preview from bytes, falling back to a data URI iframe."""
    availability = _pdf_preview_availability()
    if availability["available"]:
        try:
            st.pdf(pdf_bytes, height=height)
            return
        except Exception as exc:
            st.warning(
                f"{_label(labels, 'pdf_preview_viewer_failed', 'PDF preview failed. Open / Download still work.')}: {exc}"
            )
    else:
        warning_key = (
            "pdf_preview_dependency_missing"
            if availability["reason"] == "dependency_missing"
            else "pdf_preview_unavailable"
        )
        st.warning(
            _label(
                labels,
                warning_key,
                _label(labels, "pdf_preview_unavailable", "PDF preview is unavailable. Open / Download still work."),
            )
        )

    try:
        _render_pdf_iframe_fallback(pdf_bytes, height=height)
    except Exception as exc:
        st.warning(
            f"{_label(labels, 'pdf_preview_viewer_failed', 'PDF preview failed. Open / Download still work.')}: {exc}"
        )


def _internal_paths(config) -> dict[str, Path]:
    structured_chunks_env = os.getenv("LAB_STRUCTURED_CHUNKS_PATH", "")
    structured_index_env = os.getenv("LAB_STRUCTURED_INDEX_PATH", "")
    standard_chunks = Path(config.lab_chunks_path) if config.lab_chunks_path else Path()
    standard_index = Path(config.lab_index_path) if config.lab_index_path else Path()
    chunks_resolution = resolve_internal_chunks_path(
        structured_chunks_path=structured_chunks_env,
        standard_chunks_path=standard_chunks,
    )
    index_resolution = resolve_internal_tfidf_index_path(
        structured_index_path=structured_index_env,
        standard_index_path=standard_index,
    )
    return {
        "pdf_root": Path(config.lab_pdf_root) if config.lab_pdf_root else Path(),
        "catalog": Path(config.lab_catalog_path) if config.lab_catalog_path else Path(),
        "chunks": standard_chunks,
        "resolved_chunks": chunks_resolution["path"],
        "structured_chunks": Path(structured_chunks_env) if structured_chunks_env else Path(),
        "index": standard_index,
        "rag_index": index_resolution["path"],
        "structured_index": Path(structured_index_env) if structured_index_env else Path(),
        "vector": Path(os.getenv("LAB_VECTOR_PATH", "")) if os.getenv("LAB_VECTOR_PATH", "") else Path(),
        "path_warnings": list(chunks_resolution["warnings"]) + list(index_resolution["warnings"]),
        "path_errors": list(chunks_resolution["errors"]) + list(index_resolution["errors"]),
        "index_path_warnings": list(index_resolution["warnings"]),
        "index_path_errors": list(index_resolution["errors"]),
        "chunks_path_warnings": list(chunks_resolution["warnings"]),
        "chunks_path_errors": list(chunks_resolution["errors"]),
    }


def _active_paths(config) -> dict:
    if config.kb_mode == "internal":
        paths = _internal_paths(config)
        return {
            "index": paths["index"],
            "rag_index": paths["rag_index"],
            "vector": paths["vector"] if str(paths["vector"]) else None,
            "catalog": paths["catalog"],
            "metadata": None,
            "pdf_root": paths["pdf_root"],
            "path_warnings": paths.get("path_warnings", []),
            "path_errors": paths.get("path_errors", []),
            "index_path_warnings": paths.get("index_path_warnings", []),
            "index_path_errors": paths.get("index_path_errors", []),
            "chunks_path_warnings": paths.get("chunks_path_warnings", []),
            "chunks_path_errors": paths.get("chunks_path_errors", []),
        }
    return {
        "index": INDEX_PATH,
        "rag_index": RAG_INDEX_PATH if RAG_INDEX_PATH.exists() else INDEX_PATH,
        "vector": VECTOR_PATH,
        "catalog": None,
        "metadata": METADATA_PATH,
        "pdf_root": None,
        "path_warnings": [],
        "path_errors": [],
        "index_path_warnings": [],
        "index_path_errors": [],
        "chunks_path_warnings": [],
        "chunks_path_errors": [],
    }


def _asset_status(config) -> dict:
    if config.kb_mode == "internal":
        paths = _internal_paths(config)
        return get_internal_asset_status(paths["catalog"], paths["chunks"], paths["index"])
    return get_demo_asset_status(CHUNKS_PATH, METADATA_PATH, INDEX_PATH)


def _render_status_summary(status: dict, labels: dict[str, str]) -> None:
    ready = bool(status.get("index_exists")) and bool(status.get("chunks_exists"))
    st.caption(f"{_label(labels, 'mode', 'Mode')}: {status.get('mode', 'demo')} | Ready: {str(ready).lower()}")
    if status.get("snapshot_id"):
        st.caption(f"{_label(labels, 'current_kb_snapshot', 'Current KB Snapshot')}: {status.get('snapshot_id')}")


def _render_information_panels(status: dict, labels: dict[str, str], kb_mode: str, *, container=st) -> None:
    with container.expander(_label(labels, "system_info", "System Info")):
        st.write(f"{_label(labels, 'mode', 'Mode')}: `{kb_mode}`")
        st.write(f"{_label(labels, 'chunks', 'Chunks')}: `{status.get('chunks_exists', False)}`")
        st.write(f"{_label(labels, 'index', 'Index')}: `{status.get('index_exists', False)}`")
        st.write(f"{_label(labels, 'chunk_count', 'Chunk Count')}: `{status.get('chunk_count', 0)}`")
        if status.get("catalog_path"):
            st.write(f"{_label(labels, 'catalog', 'Catalog')}: `{status.get('catalog_path')}`")

    with container.expander(_label(labels, "knowledge_base_version", "Knowledge Base Version")):
        st.write(f"{_label(labels, 'current_application_version', 'Current Application Version')}: `v{__version__}`")
        if status.get("snapshot_available"):
            st.write(f"{_label(labels, 'current_kb_snapshot', 'Current KB Snapshot')}: `{status.get('snapshot_id')}`")
            st.write(f"{_label(labels, 'snapshot_kind', 'Snapshot Kind')}: `{status.get('snapshot_kind', '-')}`")
            st.write(f"{_label(labels, 'created_at', 'Created At')}: `{status.get('snapshot_created_at', '-')}`")
            st.write(f"{_label(labels, 'document_count', 'Document Count')}: `{status.get('snapshot_document_count', 0)}`")
            st.write(f"{_label(labels, 'chunk_count', 'Chunk Count')}: `{status.get('snapshot_chunk_count', 0)}`")
        else:
            st.caption(_label(labels, "snapshot_unavailable", "Snapshot unavailable"))
        records = list(status.get("snapshot_records") or [])
        if records:
            st.markdown(f"**{_label(labels, 'snapshot_records', 'Snapshot Records')}**")
            for item in reversed(records[-5:]):
                st.write(f"- `{item.get('snapshot_id', '-')}` | `{item.get('snapshot_kind', '-')}` | `{item.get('created_at', '-')}`")
        else:
            st.caption(_label(labels, "no_snapshot_records_available", "No snapshot records available."))

    with container.expander(_label(labels, "local_only_disclaimer", "Local-only and Disclaimer")):
        st.write(_label(labels, "local_only_note", "This UI runs locally. The runtime UI uses Ollama/API; mock is reserved for tests and evaluation."))
        st.write("AI answers are not plagiarism detection and should not be used for thesis ghostwriting.")
        st.write("No file upload workflow is implemented.")

    with container.expander(_label(labels, "technical_details", "Technical Details")):
        st.write(f"{_label(labels, 'development_stage', 'Release Marker')}: `{DEVELOPMENT_STAGE}`")
        st.write(f"{_label(labels, 'chunks_path', 'Chunks Path')}: `{status.get('chunks_path', '-')}`")
        st.write(f"{_label(labels, 'index_path', 'Index Path')}: `{status.get('index_path', '-')}`")
        if status.get("snapshot_manifest_path"):
            st.write(f"manifest: `{status.get('snapshot_manifest_path')}`")
        if status.get("snapshot_history_path"):
            st.write(f"history: `{status.get('snapshot_history_path')}`")
        if status.get("snapshot_record_dir"):
            st.write(f"records: `{status.get('snapshot_record_dir')}`")


def _render_ai_answer_result(result: dict, labels: dict[str, str], *, key_prefix: str, config=None) -> None:
    for error in result.get("errors", []):
        st.error(error)
    classified = classify_ai_warnings(result.get("warnings", []))
    for warning in classified["important"]:
        st.warning(warning)
    metadata_for_messages = result.get("metadata") or {}
    if "ai_retrieval_returned_fewer_sources_than_requested" in result.get("warnings", []):
        st.caption(
            _label(labels, "ai_retrieval_fewer_sources_message", "Requested {requested} sources; found {actual} usable papers.").format(
                requested=metadata_for_messages.get("ai_retrieval_requested_top_k", metadata_for_messages.get("retrieval_target_paper_count", "-")),
                actual=metadata_for_messages.get("ai_retrieval_actual_source_count", metadata_for_messages.get("retrieval_deduped_paper_count", "-")),
            )
        )
    if "ai_context_truncated_to_budget" in result.get("warnings", []):
        st.caption(_label(labels, "context_truncated_to_budget", "AI context was truncated to the provider budget."))
    if result.get("answer_markdown"):
        st.markdown(result["answer_markdown"])
    if result.get("citations"):
        st.markdown(f"**{_label(labels, 'citations', 'Citations')}**")
        for citation in result["citations"]:
            st.write(f"- `{citation}`")
    source_mappings = list((result.get("metadata") or {}).get("source_mappings") or [])
    if source_mappings:
        enriched_mappings = source_mappings
        if config is not None and source_mappings and all(
            mapping.get("source_type") == "retrieval" for mapping in source_mappings
        ):
            paths = _active_paths(config)
            enriched_mappings = enrich_ai_retrieved_sources_with_catalog(
                source_mappings,
                catalog_path=paths.get("catalog"),
                pdf_root=paths.get("pdf_root"),
            )
        payload = build_ai_sources_display_payload(enriched_mappings)
        if payload["mode"] == "cards" and config is not None:
            st.markdown(f"**{_label(labels, 'ai_retrieved_sources', 'AI-retrieved sources')}**")
            for mapping in payload["sources"]:
                item = dict(mapping.get("source_item") or {})
                item.setdefault("rank", mapping.get("retrieval_rank") or 0)
                item.setdefault("title", mapping.get("title", ""))
                item.setdefault("citation", mapping.get("citation", ""))
                item.setdefault("score", mapping.get("score"))
                _render_paper_result_card(item, config, labels, key_prefix=f"{key_prefix}_retrieved_pdf")
        else:
            st.markdown(f"**{_label(labels, 'sources_used_by_ai', 'Sources used by AI')}**")
            for mapping in payload["sources"]:
                source_type = mapping.get("source_type", "")
                if source_type == "current_topic_candidates":
                    rank_label = f"{_label(labels, 'topic_candidate', 'Topic candidate')} {mapping.get('visible_rank') or ''}".strip()
                elif source_type == "retrieval":
                    rank_label = f"{_label(labels, 'retrieval_result', 'Retrieval result')} {mapping.get('retrieval_rank') or ''}".strip()
                else:
                    rank_label = f"{_label(labels, 'page_result', 'Page result')} {mapping.get('visible_rank') or ''}".strip()
                details = [str(mapping.get("alias", "")), rank_label]
                if mapping.get("title"):
                    details.append(str(mapping.get("title")))
                if mapping.get("citation"):
                    details.append(str(mapping.get("citation")))
                if mapping.get("score") not in (None, ""):
                    try:
                        details.append(f"{_label(labels, 'similarity', 'Similarity')}: {float(mapping.get('score')):.4f}")
                    except (TypeError, ValueError):
                        details.append(f"{_label(labels, 'similarity', 'Similarity')}: {mapping.get('score')}")
                st.write(" · ".join(part for part in details if part))
    st.caption(
        f"{_label(labels, 'retrieved_count', 'Retrieved Count')}={result.get('retrieved_count', 0)} "
        f"{_label(labels, 'provider', 'Provider')}={result.get('provider', '')} "
        f"{_label(labels, 'model', 'Model')}={result.get('model', '')}"
    )
    with st.expander(_label(labels, "technical_details", "Technical Details")):
        st.caption(_label(labels, "technical_warning_note", "Routine technical warnings are hidden here."))
        st.write(
            {
                "warnings": result.get("warnings", []),
                "hidden_warnings": classified["hidden"],
                "metadata": result.get("metadata", {}),
                "provider": result.get("provider", ""),
                "retrieval_mode": result.get("retrieval_mode", ""),
                "model": result.get("model", ""),
                "retrieved_count": result.get("retrieved_count", 0),
            }
        )


def _provider_controls(prefix: str, labels: dict[str, str], defaults: dict | None = None) -> dict:
    defaults = defaults or {}
    default_provider = normalize_runtime_provider(defaults.get("llm_provider", defaults.get("provider", "ollama")))
    provider_key = f"{prefix}_provider"
    if st.session_state.get(provider_key) not in (None, *LOCAL_AI_LLM_PROVIDER_OPTIONS):
        st.session_state[provider_key] = "ollama"
    provider_index = LOCAL_AI_LLM_PROVIDER_OPTIONS.index(default_provider) if default_provider in LOCAL_AI_LLM_PROVIDER_OPTIONS else 0
    provider = st.selectbox(
        _label(labels, "llm_provider", "LLM Provider"),
        LOCAL_AI_LLM_PROVIDER_OPTIONS,
        index=provider_index,
        key=provider_key,
    )
    controls = {"provider": provider}
    controls["llm_profile_configured"] = bool(defaults.get("llm_profile_configured", False))
    controls["llm_profile_name"] = defaults.get("llm_profile_name", "")
    if not controls["llm_profile_configured"]:
        st.info(_label(labels, "llm_profile_missing", "No LLM profile found. Run .\\scripts\\configure_llm.ps1 to enable AI answers."))
    if provider == "ollama":
        st.caption(_label(labels, "ollama_local_requirement", "Ollama must be running locally. Start Ollama or switch to API."))
        controls["ollama_model"] = st.text_input(
            _label(labels, "ollama_model", "Ollama model"),
            value=defaults.get("ollama_model", ""),
            placeholder=_label(labels, "ollama_model_placeholder", "Run configure_llm.ps1 or enter an installed model name"),
            key=f"{prefix}_ollama_model",
        )
        controls["ollama_base_url"] = st.text_input(
            _label(labels, "ollama_base_url", "Ollama base URL"),
            value=defaults.get("ollama_base_url", ""),
            placeholder="http://localhost:11434",
            key=f"{prefix}_ollama_base_url",
        )
        controls["ollama_temperature"] = float(
            st.number_input(
                _label(labels, "ollama_temperature", "Ollama Temperature"),
                min_value=0.0,
                max_value=2.0,
                value=float(defaults.get("ollama_temperature", 0.2)),
                step=0.1,
                key=f"{prefix}_ollama_temperature",
            )
        )
        controls["ollama_num_ctx"] = int(
            st.number_input(
                _label(labels, "ollama_num_ctx", "Ollama Context Window"),
                min_value=512,
                max_value=32768,
                value=int(defaults.get("ollama_num_ctx", 4096)),
                step=512,
                key=f"{prefix}_ollama_num_ctx",
            )
        )
        controls["ollama_num_predict"] = int(
            st.number_input(
                _label(labels, "ollama_num_predict", "Ollama Max Output Tokens"),
                min_value=1,
                max_value=8192,
                value=int(defaults.get("ollama_num_predict", 1200)),
                step=100,
                key=f"{prefix}_ollama_num_predict",
            )
        )
    elif provider == "api":
        st.caption(_label(labels, "api_notice", "API calls send retrieved snippets to the configured service."))
        controls["api_base_url"] = st.text_input(
            _label(labels, "api_base_url", "API Base URL"),
            value=defaults.get("api_base_url", ""),
            key=f"{prefix}_api_base_url",
        )
        controls["api_model"] = st.text_input(
            _label(labels, "api_model", "API Model"),
            value=defaults.get("api_model", ""),
            key=f"{prefix}_api_model",
        )
        controls["api_key"] = st.text_input(_label(labels, "api_key", "API Key"), value=defaults.get("api_key", ""), type="password", key=f"{prefix}_api_key")
        controls["api_max_tokens"] = int(
            st.number_input(
                _label(labels, "api_max_tokens", "API Max Tokens"),
                min_value=1,
                max_value=8000,
                value=int(defaults.get("api_max_tokens", 1200)),
                key=f"{prefix}_api_max_tokens",
            )
        )
        controls["api_temperature"] = float(
            st.number_input(
                _label(labels, "api_temperature", "API Temperature"),
                min_value=0.0,
                max_value=2.0,
                value=float(defaults.get("api_temperature", 0.2)),
                step=0.1,
                key=f"{prefix}_api_temperature",
            )
        )
    return controls


def _provider_configuration_error(settings: dict, labels: dict[str, str]) -> str:
    provider = settings.get("provider", "ollama")
    if provider == "ollama":
        if not settings.get("ollama_model"):
            return _label(labels, "ollama_model_missing_config", "Ollama model is required. Run .\\scripts\\configure_llm.ps1 or enter an installed model name.")
        if not settings.get("ollama_base_url"):
            return _label(labels, "ollama_base_url_missing_config", "Ollama Base URL is required. Run .\\scripts\\configure_llm.ps1 or enter the Ollama server URL.")
    if provider == "api" and (not settings.get("api_base_url") or not settings.get("api_model") or not settings.get("api_key")):
        return _label(labels, "api_profile_missing_config", "API Base URL, API Model, and API Key are required before calling the API provider.")
    return ""


def _context_source_label(option: str, labels: dict[str, str]) -> str:
    if option == "retrieval":
        return _label(labels, "ai_new_retrieval", "AI new retrieval")
    return _label(labels, "current_visible_results", "Current visible results")


def _context_summary(labels: dict[str, str], settings: dict) -> str:
    count = int(settings.get("ai_context_count", 0) or 0)
    if settings.get("context_source") == "retrieval":
        return _label(labels, "ai_will_run_new_retrieval", "AI will run a new retrieval.").format(count=count)
    if count <= 0:
        key = settings.get("empty_context_message_key", "please_run_search_first_or_new_retrieval")
        return _label(labels, key, "Please run a search first, or choose New retrieval in advanced settings.")
    return _label(
        labels,
        "ai_will_use_current_visible_results",
        "Using current visible results: AI will answer using the {count} papers currently shown.",
    ).format(count=count)


def _render_panel_ai_settings(
    prefix: str,
    labels: dict[str, str],
    defaults: dict,
    *,
    visible_items: list[dict] | None = None,
    visible_top_k: int | None = None,
    current_source_type: str = "current_search_results",
    empty_context_message_key: str = "please_run_search_first_or_new_retrieval",
    current_count_label_key: str = "use_first_n_visible_results",
) -> dict:
    visible_items = list(visible_items or [])
    language_choice = st.selectbox(
        _label(labels, "answer_language", "Answer language"),
        LANGUAGE_OPTIONS,
        index=0,
        format_func=lambda option: _language_label(option, labels),
        key=f"{prefix}_language",
    )
    settings = {
        "panel_local_settings": True,
        "override_enabled": False,
        "language_choice": language_choice,
        "language": _resolve_answer_language(language_choice, defaults.get("ui_language", "zh")),
    }
    settings.update(_provider_controls(prefix, labels, build_global_ai_settings(defaults)))
    context_source = current_source_type
    eligible_items, omitted_contexts = filter_ai_eligible_contexts(visible_items)
    include_low_similarity_contexts = False
    ai_context_count = max_current_context_count(len(eligible_items), visible_top_k)
    retrieval_mode = "hybrid"
    with st.expander(_label(labels, "panel_advanced_settings", "Panel advanced settings")):
        current_label_key = "current_topic_candidates" if current_source_type == "current_topic_candidates" else "current_visible_results"
        source_choice = st.selectbox(
            _label(labels, "context_source", "Context source"),
            ("current", "retrieval"),
            index=0,
            format_func=lambda option: _label(labels, current_label_key, "Current visible results") if option == "current" else _context_source_label(option, labels),
            key=f"{prefix}_context_source",
        )
        if source_choice == "current":
            context_source = current_source_type
            include_low_similarity_contexts = st.checkbox(
                _label(labels, "include_low_similarity_results", "Include low-similarity results"),
                value=False,
                help=_label(labels, "include_low_similarity_results_help", ""),
                key=f"{prefix}_include_low_similarity",
            )
            eligible_items, omitted_contexts = filter_ai_eligible_contexts(
                visible_items,
                include_low_similarity_contexts=include_low_similarity_contexts,
            )
            if include_low_similarity_contexts:
                st.caption(_label(labels, "low_similarity_context_quality_warning", "Low-similarity results may increase token usage and reduce answer quality."))
            maximum = max_current_context_count(len(eligible_items), visible_top_k)
            if maximum > 0:
                count_key = f"{prefix}_current_context_count"
                current_count_value = int(st.session_state.get(count_key, maximum) or maximum)
                if current_count_value > maximum:
                    st.session_state[count_key] = maximum
                elif current_count_value < 1:
                    st.session_state[count_key] = 1
                ai_context_count = int(
                    st.number_input(
                        _label(labels, current_count_label_key, "Use first N visible results"),
                        min_value=1,
                        max_value=maximum,
                        value=maximum,
                        key=count_key,
                    )
                )
            else:
                ai_context_count = 0
                st.caption(_label(labels, empty_context_message_key, "Please run a search first, or choose new retrieval."))
            if omitted_contexts and not include_low_similarity_contexts:
                st.caption(
                    _label(labels, "low_quality_contexts_omitted_message", "Omitted {count} low-quality contexts.").format(
                        count=len(omitted_contexts)
                    )
                )
        else:
            context_source = "retrieval"
            retrieval_mode = st.selectbox(
                _label(labels, "retrieval_mode", "Retrieval mode"),
                ("hybrid", "tfidf", "vector"),
                index=0,
                key=f"{prefix}_retrieval_mode",
            )
            st.caption(_label(labels, "ai_retrieval_token_cost_notice", "AI will run a new retrieval and use newly retrieved context; API input tokens and cost depend on the retrieval count."))
            provider_limit = get_ai_retrieval_top_k_limit(settings.get("provider", "ollama"))
            if settings.get("provider") == "ollama":
                st.caption(_label(labels, "ollama_large_top_k_notice", "Local Ollama may be slow with larger Top K; use API for more sources."))
            retrieval_top_k_key = f"{prefix}_retrieval_top_k"
            requested_retrieval_top_k = int(st.session_state.get(retrieval_top_k_key, int(defaults.get("ai_top_k", 3))) or 3)
            clamped_retrieval_top_k, clamped_for_provider, _limit = clamp_ai_retrieval_top_k_for_provider(
                requested_retrieval_top_k,
                settings.get("provider", "ollama"),
            )
            if clamped_for_provider:
                st.session_state[retrieval_top_k_key] = clamped_retrieval_top_k
            ai_context_count = int(
                st.number_input(
                    _label(labels, "ai_retrieval_top_k", "AI retrieval Top K"),
                    min_value=1,
                    max_value=provider_limit,
                    value=clamped_retrieval_top_k,
                    help=_label(labels, "ai_retrieval_top_k_help", ""),
                    key=retrieval_top_k_key,
                )
            )
            if clamped_for_provider:
                settings.setdefault("warnings", []).append("ai_retrieval_top_k_clamped_for_provider")
        settings["context_source"] = context_source
        settings["use_current_context"] = context_source != "retrieval"
        settings["ai_context_count"] = ai_context_count
        settings["top_k"] = ai_context_count
        settings["retrieval_mode"] = retrieval_mode
        settings["empty_context_message_key"] = empty_context_message_key
        settings["visible_result_count"] = len(visible_items)
        settings["eligible_context_count"] = len(eligible_items)
        settings["omitted_context_count"] = len(omitted_contexts) if not include_low_similarity_contexts else 0
        settings["include_low_similarity_contexts"] = include_low_similarity_contexts
        settings["warnings"] = settings.get("warnings", [])
    st.caption(_settings_summary(labels, settings))
    st.caption(_context_summary(labels, settings))
    return settings


def _render_pdf_actions(item: dict, config, labels: dict[str, str], *, key_prefix: str = "pdf") -> None:
    doc_id = str(item.get("doc_id") or "")
    rank = item.get("rank", 0)
    try:
        rank_for_key = int(rank or 0)
    except (TypeError, ValueError):
        rank_for_key = 0
    preview_state_key = make_pdf_preview_state_key(key_prefix, item, rank_for_key)
    preview_visible = bool(st.session_state.get(preview_state_key, False))
    metadata: dict | None = None
    pdf_error = ""
    paths = _internal_paths(config) if config.kb_mode == "internal" else {}
    try:
        if config.kb_mode == "internal" and doc_id:
            metadata = build_pdf_action_metadata(paths["catalog"], doc_id, paths["pdf_root"])
        else:
            pdf_error = _label(labels, "pdf_unavailable", "PDF unavailable")
    except Exception as exc:
        pdf_error = str(exc)

    col1, col2, col3 = st.columns(3)
    with col1:
        if st.button(
            _label(labels, "hide_preview", "Hide Preview") if preview_visible else _label(labels, "preview_pdf", "Preview PDF"),
            key=f"{key_prefix}_toggle_preview_{doc_id or 'none'}_{rank}",
            disabled=metadata is None,
        ):
            toggle_pdf_preview_state(st.session_state, preview_state_key)
            st.rerun()
    with col2:
        if st.button(
            _label(labels, "open_pdf", "Open PDF"),
            key=f"{key_prefix}_open_{doc_id or 'none'}_{rank}",
            disabled=metadata is None,
        ):
            try:
                open_pdf(resolve_doc_id_to_pdf(paths["catalog"], doc_id, paths["pdf_root"]), paths["pdf_root"])
                st.success(_label(labels, "opened_pdf", "Opened PDF"))
            except Exception as exc:
                st.error(str(exc))
    with col3:
        download_data = b""
        download_disabled = metadata is None
        if metadata is not None:
            try:
                download_data = get_pdf_download_bytes(paths["catalog"], doc_id, paths["pdf_root"])
                download_disabled = False
            except Exception as exc:
                st.caption(f"{_label(labels, 'download_unavailable', 'Download unavailable')}: {exc}")
        st.download_button(
            _label(labels, "download_pdf", "Download PDF"),
            data=download_data,
            file_name=_safe_pdf_filename(item),
            mime="application/pdf",
            key=f"{key_prefix}_download_{doc_id or 'none'}_{rank}",
            disabled=download_disabled,
        )
    if metadata is None:
        st.caption(f"{_label(labels, 'pdf_not_resolved', _label(labels, 'pdf_unavailable', 'PDF unavailable'))}: {pdf_error}")
    if metadata is not None and bool(st.session_state.get(preview_state_key, False)):
        payload = resolve_pdf_preview_payload(Path(metadata["pdf_path"]), pdf_root=paths["pdf_root"])
        if not payload["ok"]:
            st.warning(
                f"{_label(labels, 'pdf_not_resolved', _label(labels, 'pdf_unavailable', 'PDF unavailable'))}: {payload['reason']}"
            )
        else:
            _render_pdf_preview_bytes(payload["bytes"], labels, height=650)


def _paper_card_metadata(item: dict, labels: dict[str, str]) -> list[str]:
    parts: list[str] = []
    context = build_paper_card_context(item, labels)
    if context.get("year"):
        parts.append(f"{_label(labels, 'year', 'Year')}: {context['year']}")
    if context.get("advisor"):
        parts.append(f"{_label(labels, 'advisor', 'Advisor')}: {context['advisor']}")
    if context.get("citation"):
        parts.append(f"{_label(labels, 'citation', 'Citation')}: {context['citation']}")
    if context.get("used_aliases"):
        parts.append(f"{context['used_aliases_label']}: {', '.join(context['used_aliases'])}")
    if context.get("similarity"):
        parts.append(f"{context['similarity_label']}: {context['similarity']}")
    if context.get("matched_count"):
        parts.append(f"{context['matched_label']}: {context['matched_count']}")
    return parts


def _render_paper_result_card(item: dict, config, labels: dict[str, str], *, key_prefix: str) -> None:
    context = build_paper_card_context(item, labels)
    with st.container(border=True):
        st.markdown(f"**{context['rank']}. {context['title']}**")
        metadata = _paper_card_metadata(item, labels)
        if metadata:
            st.caption(" | ".join(metadata))
        matched_chunks = item.get("matched_chunks") or []
        with st.expander(_label(labels, "snippet_preview", "Snippet preview")):
            st.write(context["snippet"])
            for chunk in matched_chunks[:3]:
                if chunk.get("snippet"):
                    chunk_parts = [str(part) for part in (chunk.get("alias"), chunk.get("citation")) if part]
                    chunk_prefix = f"{' · '.join(chunk_parts)}: " if chunk_parts else ""
                    st.write(f"- {chunk_prefix}{chunk.get('snippet')}")
        _render_pdf_actions(item, config, labels, key_prefix=key_prefix)


def _render_search_tab(config, labels: dict[str, str], defaults: dict) -> None:
    paths = _active_paths(config)
    query = st.text_input(
        _label(labels, "search_keywords_label", "Search keywords (determine candidate papers below)"),
        help=_label(labels, "search_keywords_help", ""),
        key="search_query",
    )
    top_k = int(defaults.get("search_top_k", 5))
    st.caption(f"{_label(labels, 'global_defaults_active', 'Using global defaults')}: {_label(labels, 'search_top_k', 'Search Top K')}={top_k}")
    if st.button(_label(labels, "search_button", "Search")):
        result = run_search(paths["index"], query, top_k=int(top_k), kb_mode=config.kb_mode, catalog_path=paths["catalog"], metadata_path=paths["metadata"])
        persist_search_result(st.session_state, query, result)
        st.session_state["search_results_for_ai"] = result.get("results", [])
    result = st.session_state.get("last_search_results")
    if result:
        results = result.get("results", [])
        maybe_clear_pdf_preview_state_on_results_change(
            st.session_state,
            "search_pdf_preview_",
            build_pdf_preview_results_signature(results),
            "search_pdf_preview_results_signature",
        )
        for item in results:
            _render_paper_result_card(item, config, labels, key_prefix="search_pdf")

    st.divider()
    st.subheader(_label(labels, "local_ai_answer", "Local AI Answer"))
    _sync_followup_question_default(
        st.session_state,
        question_key="search_ai_question",
        source_value=st.session_state.get("last_search_query", ""),
        marker_key="last_search_query_for_ai_autofill",
    )
    ai_question = st.text_input(
        _label(labels, "ask_current_search_results_label", "Ask about the current search results"),
        help=_label(labels, "ask_current_search_results_help", ""),
        key="search_ai_question",
    )
    current_results_for_ai = list(st.session_state.get("search_results_for_ai", []) or [])
    settings = _render_panel_ai_settings(
        "search_ai",
        labels,
        defaults,
        visible_items=current_results_for_ai,
        visible_top_k=int(defaults.get("search_top_k", 5)),
        current_source_type="current_search_results",
    )
    if settings["context_source"] == "current_search_results":
        eligible_results_for_ai, _omitted_results_for_ai = filter_ai_eligible_contexts(
            current_results_for_ai,
            include_low_similarity_contexts=bool(settings.get("include_low_similarity_contexts", False)),
        )
        settings["source_mappings"] = build_ai_source_mappings(
            eligible_results_for_ai,
            source_type="current_search_results",
            limit=int(settings["ai_context_count"]),
        )
    current_signature = _result_signature(
        query=ai_question,
        settings=settings,
        retrieval_mode=settings["retrieval_mode"],
        context_source=settings["context_source"],
        use_current_context=bool(settings["use_current_context"]),
    )
    if st.button(_label(labels, "generate_local_ai_answer", "Generate Local AI Answer")):
        provider_error = _provider_configuration_error(settings, labels)
        if provider_error:
            st.error(provider_error)
        elif settings["context_source"] == "retrieval" and paths.get("index_path_errors"):
            st.error("; ".join(paths.get("index_path_errors") or []))
        elif settings["context_source"] == "current_search_results" and not current_results_for_ai:
            st.error(_label(labels, "please_run_search_first_or_new_retrieval", "Please run a search first, or choose new retrieval."))
        elif settings["context_source"] == "current_search_results" and int(settings.get("eligible_context_count", 0) or 0) <= 0:
            st.error(_label(labels, "no_ai_eligible_contexts", "Current page results do not contain enough usable AI context. Adjust the query or choose AI new retrieval."))
        else:
            with st.spinner(_label(labels, "generating_local_ai_answer", "Generating local AI answer, please wait...")):
                result = run_local_ai_answer(
                    query=ai_question,
                    retrieval_mode=settings["retrieval_mode"],
                    llm_provider=settings["provider"],
                    language=settings["language"],
                    top_k=int(settings["ai_context_count"]),
                    tfidf_index_path=paths["rag_index"],
                    vector_persist_dir=paths["vector"],
                    vector_collection=VECTOR_COLLECTION,
                    embedding_provider="hash",
                    ollama_base_url=settings.get("ollama_base_url", ""),
                    ollama_model=settings.get("ollama_model", ""),
                    ollama_temperature=float(settings.get("ollama_temperature", 0.2)),
                    ollama_num_ctx=int(settings.get("ollama_num_ctx", 4096)),
                    ollama_num_predict=int(settings.get("ollama_num_predict", 1200)),
                    api_base_url=settings.get("api_base_url"),
                    api_model=settings.get("api_model"),
                    api_key=settings.get("api_key"),
                    api_max_tokens=int(settings.get("api_max_tokens", 1200)),
                    api_temperature=float(settings.get("api_temperature", 0.2)),
                    current_search_results=current_results_for_ai,
                    use_current_search_results=bool(settings["use_current_context"]),
                    include_low_similarity_contexts=bool(settings.get("include_low_similarity_contexts", False)),
                )
                if settings["context_source"] == "retrieval" and paths.get("index_path_warnings"):
                    result["warnings"] = list(result.get("warnings", [])) + list(paths.get("index_path_warnings") or [])
                    metadata = dict(result.get("metadata") or {})
                    metadata["index_path_warnings"] = list(paths.get("index_path_warnings") or [])
                    metadata["resolved_tfidf_index_path"] = str(paths["rag_index"])
                    result["metadata"] = metadata
                result = maybe_replace_timeout_errors(result, provider=settings["provider"], labels=labels)
                st.session_state["local_ai_answer_result"] = _attach_result_signature(result, current_signature)
    if st.session_state.get("local_ai_answer_result"):
        if _is_result_stale(st.session_state["local_ai_answer_result"], current_signature):
            st.warning(_label(labels, "settings_or_sources_changed", "Settings or sources changed. Please regenerate."))
        _render_ai_answer_result(st.session_state["local_ai_answer_result"], labels, key_prefix="search_ai", config=config)


def _render_topic_tab(config, labels: dict[str, str], defaults: dict) -> None:
    paths = _active_paths(config)
    topic = st.text_input(_label(labels, "topic_to_analyze_label", "Topic to analyze (generates candidate papers and risk analysis)"), help=_label(labels, "topic_to_analyze_help", ""), key="topic_query")
    top_k = int(defaults.get("topic_top_k", defaults.get("search_top_k", 5)))
    st.caption(f"{_label(labels, 'global_defaults_active', 'Using global defaults')}: {_label(labels, 'topic_top_k', 'Topic Top K')}={top_k}")
    default_report_language = defaults.get("ui_language", "zh")
    report_index = CONCRETE_LANGUAGE_OPTIONS.index(default_report_language) if default_report_language in CONCRETE_LANGUAGE_OPTIONS else 0
    report_language = st.selectbox(
        _label(labels, "report_language", "Report language"),
        CONCRETE_LANGUAGE_OPTIONS,
        index=report_index,
        key="topic_language",
    )
    topic_report_signature = {
        "topic": topic,
        "language": report_language,
        "top_k": int(top_k),
        "provider": "mock",
    }
    if st.button(_label(labels, "generate_topic_analysis", "Generate Topic Analysis")):
        result = run_topic_analysis(paths["index"], topic, top_k=int(top_k), language=report_language, kb_mode=config.kb_mode, catalog_path=paths["catalog"], metadata_path=paths["metadata"])
        result["metadata"] = {
            "result_signature": topic_report_signature,
            "result_language": report_language,
            "query": topic,
            "top_k": int(top_k),
            "provider": "mock",
        }
        persist_topic_result(st.session_state, topic, result)
        st.session_state["topic_candidates_for_ai"] = result.get("references", [])
    result = st.session_state.get("last_topic_analysis")
    if result:
        if _is_result_stale(result, topic_report_signature):
            st.warning(f"{_label(labels, 'stale_result_warning', 'This result was generated with previous settings.')} {_label(labels, 'regenerate_required', 'Please regenerate to use the current settings.')}")
        col1, col2, col3 = st.columns(3)
        col1.metric(_label(labels, "risk_level", "Risk level"), str(result.get("risk_level", "-")))
        col2.metric(_label(labels, "risk_score", "Risk score"), f"{float(result.get('risk_score', 0.0)):.4f}")
        col3.metric(_label(labels, "result_count", "Result count"), str(result.get("result_count", 0)))
        st.caption(build_risk_explanation(labels))
        st.markdown(result.get("report_markdown", ""))
        references = result.get("references", [])
        if references:
            st.markdown(f"**{_label(labels, 'topic_candidates', 'Topic Candidates')}**")
            maybe_clear_pdf_preview_state_on_results_change(
                st.session_state,
                "topic_pdf_preview_",
                build_pdf_preview_results_signature(references),
                "topic_pdf_preview_results_signature",
            )
            for item in references:
                _render_paper_result_card(item, config, labels, key_prefix="topic_pdf")

    st.divider()
    st.subheader(_label(labels, "topic_ai_assist", "Topic AI Assist"))
    _sync_followup_question_default(
        st.session_state,
        question_key="topic_ai_question",
        source_value=st.session_state.get("last_topic", ""),
        marker_key="last_topic_query_for_ai_autofill",
    )
    assist_question = st.text_input(
        _label(labels, "ask_current_topic_candidates_label", "Ask about the current topic candidates"),
        help=_label(labels, "ask_current_topic_candidates_help", ""),
        key="topic_ai_question",
    )
    current_topic_candidates = list(st.session_state.get("topic_candidates_for_ai", []) or [])
    settings = _render_panel_ai_settings(
        "topic_ai",
        labels,
        defaults,
        visible_items=current_topic_candidates,
        visible_top_k=int(defaults.get("topic_top_k", defaults.get("search_top_k", 5))),
        current_source_type="current_topic_candidates",
        empty_context_message_key="please_generate_topic_candidates_first_or_new_retrieval",
        current_count_label_key="use_first_n_topic_candidates",
    )
    if settings["context_source"] == "current_topic_candidates":
        eligible_candidates_for_ai, _omitted_candidates_for_ai = filter_ai_eligible_contexts(
            current_topic_candidates,
            include_low_similarity_contexts=bool(settings.get("include_low_similarity_contexts", False)),
        )
        settings["source_mappings"] = build_ai_source_mappings(
            eligible_candidates_for_ai,
            source_type="current_topic_candidates",
            limit=int(settings["ai_context_count"]),
        )
    current_signature = _result_signature(
        query=assist_question,
        settings=settings,
        retrieval_mode=settings["retrieval_mode"],
        context_source=settings["context_source"],
        use_current_context=bool(settings["use_current_context"]),
    )
    if st.button(_label(labels, "generate_topic_ai_assist", "Generate Topic AI Assist")):
        provider_error = _provider_configuration_error(settings, labels)
        if provider_error:
            st.error(provider_error)
        elif settings["context_source"] == "retrieval" and paths.get("index_path_errors"):
            st.error("; ".join(paths.get("index_path_errors") or []))
        elif settings["context_source"] == "current_topic_candidates" and not current_topic_candidates:
            st.error(_label(labels, "please_generate_topic_candidates_first_or_new_retrieval", "Please generate topic candidates first, or choose new retrieval."))
        elif settings["context_source"] == "current_topic_candidates" and int(settings.get("eligible_context_count", 0) or 0) <= 0:
            st.error(_label(labels, "no_ai_eligible_topic_contexts", "Current topic candidates do not contain enough usable AI context. Generate better candidates or choose AI new retrieval."))
        else:
            with st.spinner(_label(labels, "generating_topic_ai_assist", "Generating topic AI assist, please wait...")):
                result = run_topic_ai_assist(
                    topic_query=assist_question,
                    topic_candidates=current_topic_candidates,
                    retrieval_mode=settings["retrieval_mode"],
                    llm_provider=settings["provider"],
                    language=settings["language"],
                    top_k=int(settings["ai_context_count"]),
                    tfidf_index_path=paths["rag_index"],
                    vector_persist_dir=paths["vector"],
                    vector_collection=VECTOR_COLLECTION,
                    embedding_provider="hash",
                    ollama_base_url=settings.get("ollama_base_url", ""),
                    ollama_model=settings.get("ollama_model", ""),
                    ollama_temperature=float(settings.get("ollama_temperature", 0.2)),
                    ollama_num_ctx=int(settings.get("ollama_num_ctx", 4096)),
                    ollama_num_predict=int(settings.get("ollama_num_predict", 1200)),
                    api_base_url=settings.get("api_base_url"),
                    api_model=settings.get("api_model"),
                    api_key=settings.get("api_key"),
                    api_max_tokens=int(settings.get("api_max_tokens", 1200)),
                    api_temperature=float(settings.get("api_temperature", 0.2)),
                    use_topic_candidates=bool(settings["use_current_context"]),
                    include_low_similarity_contexts=bool(settings.get("include_low_similarity_contexts", False)),
                )
                if settings["context_source"] == "retrieval" and paths.get("index_path_warnings"):
                    result["warnings"] = list(result.get("warnings", [])) + list(paths.get("index_path_warnings") or [])
                    metadata = dict(result.get("metadata") or {})
                    metadata["index_path_warnings"] = list(paths.get("index_path_warnings") or [])
                    metadata["resolved_tfidf_index_path"] = str(paths["rag_index"])
                    result["metadata"] = metadata
                result = maybe_replace_timeout_errors(result, provider=settings["provider"], labels=labels)
                st.session_state["topic_ai_assist_result"] = _attach_result_signature(result, current_signature)
    if st.session_state.get("topic_ai_assist_result"):
        if _is_result_stale(st.session_state["topic_ai_assist_result"], current_signature):
            st.warning(_label(labels, "settings_or_sources_changed", "Settings or sources changed. Please regenerate."))
        _render_ai_answer_result(st.session_state["topic_ai_assist_result"], labels, key_prefix="topic_ai", config=config)


def _render_structure_tab(labels: dict[str, str]) -> None:
    samples = list_demo_samples(SAMPLES_DIR)
    if not samples:
        st.warning(_label(labels, "no_demo_samples", "No demo samples found."))
        return
    selected = st.selectbox(_label(labels, "sample", "Synthetic sample"), samples)
    language = st.selectbox(_label(labels, "structure_language", "Structure language"), CONCRETE_LANGUAGE_OPTIONS, index=1, key="structure_language")
    if st.button(_label(labels, "run_structure_check", "Run Structure Check")):
        result = run_structure_check(SAMPLES_DIR / selected, language=language)
        if result["ok"]:
            st.write(f"{_label(labels, 'score', 'Score')}={result.get('score')}")
            st.write("present_sections: " + ", ".join(result.get("present_sections", [])))
            st.write("missing_sections: " + ", ".join(result.get("missing_sections", [])))
        else:
            st.error("; ".join(result.get("errors", [])))


def _render_sidebar_controls(config, labels: dict[str, str], status: dict, ui_language: str) -> dict:
    defaults: dict = {"ui_language": ui_language}
    with st.sidebar:
        st.markdown(f"### {_label(labels, 'app_title', 'ThesisAgent')}")
        st.caption(f"{_label(labels, 'application_version', 'Application Version')}: v{__version__}")
        retrieval_defaults_label = _label(labels, "retrieval_defaults", _label(labels, "global_search_settings", "Retrieval Defaults"))
        with st.expander(retrieval_defaults_label, expanded=True):
            defaults["search_top_k"] = int(
                st.number_input(
                    _label(labels, "search_top_k", "Search Top K"),
                    min_value=1,
                    max_value=20,
                    value=5,
                    key="global_search_top_k",
                )
            )
            defaults["topic_top_k"] = int(
                st.number_input(
                    _label(labels, "topic_top_k", "Topic Top K"),
                    min_value=1,
                    max_value=20,
                    value=5,
                    key="global_topic_top_k",
                )
            )
        _render_information_panels(status, labels, config.kb_mode, container=st.sidebar)
    return defaults


def main() -> None:
    config = get_app_config()
    st.set_page_config(page_title="ThesisAgent", page_icon="TA", layout="wide")
    st.markdown(DEPLOY_HIDE_CSS, unsafe_allow_html=True)
    st.title(f"ThesisAgent v{__version__}")
    initial_language = config.ui_language if config.ui_language in CONCRETE_LANGUAGE_OPTIONS else "zh"
    initial_labels = _ui_text(initial_language)
    raw_ui_language = st.sidebar.selectbox(
        _label(initial_labels, "language", "UI Language"),
        LANGUAGE_OPTIONS,
        index=0,
        format_func=lambda option: _language_label(option, initial_labels),
        key="global_ui_language",
    )
    ui_language = _resolve_ui_language(raw_ui_language, initial_language)
    labels = _ui_text(ui_language)
    status = _asset_status(config)
    defaults = _render_sidebar_controls(config, labels, status, ui_language)
    _render_status_summary(status, labels)
    tabs = st.tabs([_label(labels, "search_tab", "Search"), _label(labels, "topic_tab", "Topic Analysis"), _label(labels, "structure_tab", "Structure Check")])
    with tabs[0]:
        _render_search_tab(config, labels, defaults)
    with tabs[1]:
        _render_topic_tab(config, labels, defaults)
    with tabs[2]:
        _render_structure_tab(labels)


if __name__ == "__main__":
    main()
