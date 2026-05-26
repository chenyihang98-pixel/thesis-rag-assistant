# ThesisAgent Architecture

## Overview

ThesisAgent is a local-first thesis knowledge-base RAG and Agent application. The release runtime supports synthetic demo data and explicitly configured internal runtime assets, while keeping real thesis files outside the repository.

The default flow is deterministic and offline:

1. ingest synthetic or configured documents into chunks;
2. build TF-IDF and optional local hash-vector indexes;
3. retrieve with TF-IDF, vector, or hybrid mode;
4. optionally generate grounded local AI answers with local `ollama` or user-configured `api` in the UI, while retaining `mock` for tests and evaluation;
5. evaluate the retrieval/RAG/Agent wrappers with synthetic cases;
6. record lightweight knowledge-base snapshot metadata.

## Runtime Modes

Demo mode uses project-local synthetic data under `data/samples` and generated runtime assets under `data/processed`, `data/index`, and `data/vector`. The release workflow is `setup_demo.ps1` followed by `run_demo.ps1`; both use the project virtual environment and hash embeddings only.

Internal mode uses local ignored profiles under `.runtime/internal/`. `configure_internal.ps1` asks the user for profile name, PDF root, and language, then creates generated corpus assets under `.runtime/internal/corpora/<profile_name>/` by default. Advanced users can choose a custom work directory, but original PDFs are not copied into the project. The wizard writes `.runtime/internal/profiles/<profile_name>.json` plus `.runtime/internal/current_profile.json`. `run_internal.ps1` reads available profiles, can switch with `-Profile <profile_name>` or an interactive selection prompt, updates the current profile pointer, and exports the corresponding `LAB_*` variables for the UI. Normal UI startup checks only configured paths and does not rebuild indexes.

LLM provider settings use the same local-profile pattern under `.runtime/llm/`. `configure_llm.ps1` writes `.runtime/llm/profiles/<profile_name>.json` and `.runtime/llm/current_profile.json`, then `run_demo.ps1` and `run_internal.ps1` export `LLM_DEFAULT_PROVIDER`, `OLLAMA_*`, or `API_LLM_*` variables before starting Streamlit.

## Retrieval Pipeline

- `processing.sections` and `processing.structured_chunker` produce section-aware chunks with `embedding_text`, `display_text`, section type, heading path, and page metadata.
- `pipeline.retrieval` builds/searches TF-IDF indexes.
- `vectorstore.chroma` provides a Chroma-compatible local hash vector index for offline tests and demos.
- `retrieval.hybrid` and `retrieval.hybrid_provider` merge TF-IDF and vector results.

The hash vector implementation keeps the local vector command surface available without requiring external embeddings. Full Chroma client behavior remains an expansion point.

## LLM Providers and RAG Answer

- Runtime/UI providers: `ollama` and `api`. The Streamlit UI defaults to `ollama`; if Ollama is not running, users should start it locally or switch to `api`.
- Runtime provider defaults come from the ignored local LLM profile or environment variables. If no profile is configured, the UI prompts the user to run `configure_llm.ps1` instead of assuming a personal model name.
- CLI Ollama commands require an explicit model from `--ollama-model`, `OLLAMA_MODEL`, or the local LLM profile exported by the run scripts; source code does not hardcode a personal Ollama model default.
- Dev/test/evaluation providers: `mock`, `ollama`, and `api`. `mock` is deterministic and context-aware; it parses the RAG prompt's current contexts and citation aliases to produce stable tests/evaluation without external calls.
- `ollama` uses local `/api/chat`, UTF-8 JSON bytes, and `Content-Type: application/json; charset=utf-8`.
- `api` is an OpenAI-compatible chat-completions shell implemented with `urllib`, not the OpenAI SDK.

The RAG answer pipeline builds an allowed citation registry, supports runtime aliases such as `[1]`, canonicalizes citations, appends a reference section, strips reasoning text, and can use already-visible UI search/topic candidates as provided contexts.

The local LLM constraint chain includes:

- Ollama requests use UTF-8 JSON bytes and `Content-Type: application/json; charset=utf-8`.
- Ollama `think` defaults to `false`.
- `<think>` and visible reasoning-prefixed lines are stripped from generated answers.
- Missing canonical citations trigger a bounded retry that explicitly requires `[1]`/`[2]`/`[3]`.
- Language mismatch for `zh`/`en` triggers an answer-only rewrite prompt that contains the previous answer and citation registry, not the original retrieved context.
- Routine technical warnings remain in technical details, while unresolved mismatch/citation/provider errors stay visible.

## Agent Layer

The Agent layer is intentionally thin and local:

- `agent.router` maps explicit tasks.
- `agent.tool_runner` invokes local tools and explicit `rag_answer`.
- `agent.orchestrator` returns a unified `AgentRunResult`.

`rag_answer` is never chosen by auto routing by default. Ollama/API never become defaults.

## Evaluation Layer

The evaluation modules cover:

- Agent golden queries
- chunk quality and chunk quality gates
- retrieval mode and retrieval relevance
- semantic embedding comparison and gates
- multilingual vector smoke
- RAG answer evaluation, strict gates, and mock-vs-Ollama comparison
- Agent RAG answer evaluation, gates, and comparison
- aggregate report rendering/diffing

Tests use synthetic cases, tmp paths, mock providers, and fake/precomputed outputs. They do not call real Ollama/API or read real PDFs.

## Streamlit UI

`app.py` exposes:

- Search tab with Local AI Answer
- Topic Analysis tab with Topic AI Assist
- Structure Check tab
- sidebar defaults for UI language and page-level Search/Topic Top K
- panel-local AI controls for answer language, provider, Ollama/API settings, and advanced context-source choices
- advanced context-source controls that default to current visible results/candidates and can switch to AI new retrieval
- runtime provider choices `ollama`, `api` (`mock` remains available to CLI/tests/evaluation)
- API base URL/model/key fields only when `api` is selected
- spinner feedback for AI generation
- routine warnings hidden in technical details
- errors and important warnings shown directly
- PDF open/download and preview fallback
- system info, knowledge-base version, disclaimer, and technical details in expanders
- zh/ja/en labels for the main user-facing controls
- shared paper-card rendering for search results and topic candidates
- stale-result signatures for generated AI/topic outputs when relevant settings change

The top header shows the application version. Technical details expose the release marker and runtime paths. The UI hides Streamlit top-right local-demo chrome such as Deploy/status widgets without hiding the app body, sidebar, or tabs.

Search Local AI Answer uses currently visible search results as provided RAG contexts by default. Topic AI Assist similarly uses current topic candidates. These defaults keep citations aligned with what the user sees; when no current results exist, the panels fall back to retrieval and surface an important warning.

## Snapshot Metadata

`kb_snapshot.py` records lightweight metadata:

- snapshot id/kind/time
- mode
- document and chunk counts
- catalog/chunks/index/vector paths
- embedding provider/model
- notes
- optional records/history

Manifest/history/record files are metadata only. Full rollback requires preserving the matching catalog, chunks, TF-IDF index, vector store, and environment settings.

## Runtime Scripts

PowerShell scripts under `scripts/` wrap daily operations:

- `setup_demo.ps1`: creates `.venv`, installs `.[dev]`, generates demo assets, and writes a demo snapshot.
- `run_demo.ps1`: clears `KB_MODE`/`LAB_*`, repairs missing demo assets/snapshot, and starts Streamlit in demo mode.
- `configure_internal.ps1`: interactive internal profile wizard; after `YES`, builds missing local catalog/chunks/index/vector assets in `.runtime/internal/corpora/<profile_name>/` by default and writes the active profile.
- `configure_llm.ps1`: interactive Ollama/API profile wizard; writes ignored `.runtime/llm` profile files and `scripts/set_llm_env.local.ps1`.
- `run_internal.ps1`: selects from `.runtime/internal/profiles/*.json`, updates `.runtime/internal/current_profile.json`, sets `LAB_*`, loads the optional LLM profile, validates required assets, and starts Streamlit.
- `prepare_demo_assets.ps1`: builds demo chunks, TF-IDF indexes, and hash vector assets from `data/samples`.
- `write_demo_snapshot.ps1`: writes demo snapshot manifest/history/records.
- `write_internal_snapshot.ps1`: legacy metadata helper for already configured `LAB_*` paths.
- `clean_local_cache.ps1`, `reset_demo_assets.ps1`, and deprecated non-destructive `clean_demo_runtime.ps1`.

Generated profile and runtime files are ignored: `.runtime/`, `scripts/set_internal_env.local.ps1`, `scripts/set_llm_env.local.ps1`, `data/processed/`, `data/index/`, `data/vector/`, and demo snapshot metadata. Internal corpus workspaces live under `.runtime/internal/corpora/<profile_name>/` by default and may contain private extracted text. Scripts must not delete `.git`, `.venv`, `src`, `tests`, `docs`, `scripts`, root source files, synthetic samples, evaluation configs, PDF roots, or other profile workspaces.

## Future Work

LangGraph, LoRA, OCR, file upload, hosted deployment, and enterprise snapshot export/restore are explicitly out of the current release scope. They can be added later without changing the default local-first safety boundary.
