"""Lightweight knowledge-base snapshot metadata."""

from __future__ import annotations

import json
import os
from dataclasses import asdict, dataclass, field
from datetime import UTC, datetime
from pathlib import Path
from uuid import uuid4


DEFAULT_DEMO_SNAPSHOT_MANIFEST_PATH = Path("data/metadata/kb_snapshot_manifest.json")
DEFAULT_DEMO_SNAPSHOT_HISTORY_PATH = Path("data/metadata/kb_snapshot_history.json")
DEFAULT_DEMO_SNAPSHOT_RECORD_DIR = Path("data/metadata/kb_snapshots")
ALLOWED_SNAPSHOT_KINDS = {"dev", "demo", "internal", "release"}


@dataclass
class KbSnapshotManifest:
    snapshot_id: str
    created_at: str
    mode: str
    snapshot_kind: str = "dev"
    source_kind: str = "demo_or_internal"
    document_count: int = 0
    chunk_count: int = 0
    chunk_mode: str = ""
    catalog_path: str = ""
    chunks_path: str = ""
    index_path: str = ""
    structured_chunks_path: str = ""
    structured_index_path: str = ""
    vector_path: str = ""
    embedding_provider: str = ""
    embedding_model: str = ""
    git_branch: str = ""
    git_commit: str = ""
    notes: str = ""
    metadata: dict = field(default_factory=dict)


def make_snapshot_id(prefix: str = "kb") -> str:
    timestamp = datetime.now(UTC).strftime("%Y%m%dT%H%M%SZ")
    return f"{prefix}_{timestamp}_{uuid4().hex[:8]}"


def count_jsonl(path: Path | None) -> int:
    if path is None or not path.exists():
        return 0
    count = 0
    with path.open("r", encoding="utf-8") as handle:
        for line in handle:
            if line.strip():
                count += 1
    return count


def count_catalog_rows(path: Path | None) -> int:
    if path is None or not path.exists():
        return 0
    with path.open("r", encoding="utf-8-sig") as handle:
        lines = [line for line in handle if line.strip()]
    return max(len(lines) - 1, 0)


def get_git_branch(repo_root: Path) -> str:
    del repo_root
    return os.getenv("THESIS_AGENT_GIT_BRANCH", "").strip()


def get_git_commit(repo_root: Path) -> str:
    del repo_root
    return os.getenv("THESIS_AGENT_GIT_COMMIT", "").strip()


def get_git_branch_from_shell(repo_root: Path) -> str:
    """Deprecated compatibility shim.

    Runtime callers that need a branch name should provide
    THESIS_AGENT_GIT_BRANCH explicitly.
    """
    del repo_root
    return ""


def get_git_commit_from_shell(repo_root: Path) -> str:
    del repo_root
    return ""


def _deprecated_git_branch(repo_root: Path) -> str:
    return _run_git(repo_root, "branch", "--show-current")


def _deprecated_git_commit(repo_root: Path) -> str:
    return _run_git(repo_root, "rev-parse", "--short", "HEAD")


def build_kb_snapshot_manifest(
    *,
    mode: str,
    snapshot_id: str | None = None,
    catalog_path: Path | None = None,
    chunks_path: Path | None = None,
    index_path: Path | None = None,
    structured_chunks_path: Path | None = None,
    structured_index_path: Path | None = None,
    vector_path: Path | None = None,
    embedding_provider: str = "hash",
    embedding_model: str = "",
    snapshot_kind: str | None = None,
    chunk_mode: str = "",
    notes: str = "",
    repo_root: Path | None = None,
) -> KbSnapshotManifest:
    normalized_mode = (mode or "demo").strip().lower()
    if normalized_mode not in {"demo", "internal"}:
        raise ValueError("mode must be 'demo' or 'internal'")
    normalized_kind = _normalize_snapshot_kind(snapshot_kind or normalized_mode)
    root = (repo_root or Path.cwd()).resolve()
    selected_chunks_path = structured_chunks_path or chunks_path
    chunk_count = count_jsonl(selected_chunks_path)
    document_count = count_catalog_rows(catalog_path) if catalog_path else _count_unique_doc_ids_from_chunks(selected_chunks_path)
    return KbSnapshotManifest(
        snapshot_id=snapshot_id or make_snapshot_id("kb"),
        created_at=datetime.now(UTC).isoformat(timespec="seconds").replace("+00:00", "Z"),
        mode=normalized_mode,
        snapshot_kind=normalized_kind,
        source_kind="synthetic_demo" if normalized_mode == "demo" else "configured_internal_runtime_assets",
        document_count=document_count,
        chunk_count=chunk_count,
        chunk_mode=chunk_mode,
        catalog_path=_path_text(catalog_path),
        chunks_path=_path_text(chunks_path),
        index_path=_path_text(index_path),
        structured_chunks_path=_path_text(structured_chunks_path),
        structured_index_path=_path_text(structured_index_path),
        vector_path=_path_text(vector_path),
        embedding_provider=embedding_provider,
        embedding_model=embedding_model,
        git_branch=get_git_branch(root),
        git_commit=get_git_commit(root),
        notes=notes,
    )


def write_kb_snapshot_manifest(manifest: KbSnapshotManifest, output_path: Path) -> None:
    output_path.parent.mkdir(parents=True, exist_ok=True)
    output_path.write_text(json.dumps(asdict(manifest), ensure_ascii=False, indent=2), encoding="utf-8")


def load_kb_snapshot_manifest(path: Path | None) -> KbSnapshotManifest | None:
    if path is None or not path.exists():
        return None
    data = json.loads(path.read_text(encoding="utf-8"))
    return KbSnapshotManifest(**data)


def resolve_snapshot_manifest_path(mode: str) -> Path | None:
    normalized_mode = (mode or "demo").strip().lower()
    if normalized_mode == "internal":
        value = os.getenv("LAB_SNAPSHOT_MANIFEST_PATH", "").strip()
        return Path(value) if value else None
    value = os.getenv("KB_SNAPSHOT_MANIFEST_PATH", "").strip()
    return Path(value) if value else DEFAULT_DEMO_SNAPSHOT_MANIFEST_PATH


def resolve_snapshot_history_path(manifest_path: Path | None = None, *, mode: str = "demo") -> Path | None:
    normalized_mode = (mode or "demo").strip().lower()
    if normalized_mode == "internal":
        value = os.getenv("LAB_SNAPSHOT_HISTORY_PATH", "").strip()
        if value:
            return Path(value)
        return manifest_path.with_name("kb_snapshot_history.json") if manifest_path else None
    value = os.getenv("KB_SNAPSHOT_HISTORY_PATH", "").strip()
    if value:
        return Path(value)
    if manifest_path:
        return manifest_path.with_name("kb_snapshot_history.json")
    return DEFAULT_DEMO_SNAPSHOT_HISTORY_PATH


def append_snapshot_history(manifest: KbSnapshotManifest, history_path: Path) -> None:
    history = load_snapshot_history(history_path)
    payload = asdict(manifest)
    history = [item for item in history if item.get("snapshot_id") != manifest.snapshot_id]
    history.append(payload)
    history_path.parent.mkdir(parents=True, exist_ok=True)
    history_path.write_text(json.dumps(history, ensure_ascii=False, indent=2), encoding="utf-8")


def load_snapshot_history(history_path: Path | None) -> list[dict]:
    if history_path is None or not history_path.exists():
        return []
    try:
        data = json.loads(history_path.read_text(encoding="utf-8"))
    except json.JSONDecodeError:
        return []
    return data if isinstance(data, list) else []


def resolve_snapshot_record_dir(mode: str, manifest_path: Path | None = None) -> Path | None:
    normalized_mode = (mode or "demo").strip().lower()
    if normalized_mode == "internal":
        value = os.getenv("LAB_SNAPSHOT_RECORD_DIR", "").strip()
        if value:
            return Path(value)
        return manifest_path.with_name("kb_snapshots") if manifest_path else None
    value = os.getenv("KB_SNAPSHOT_RECORD_DIR", "").strip()
    if value:
        return Path(value)
    if manifest_path:
        return manifest_path.with_name("kb_snapshots")
    return DEFAULT_DEMO_SNAPSHOT_RECORD_DIR


def write_snapshot_record(manifest: KbSnapshotManifest, record_dir: Path) -> Path:
    record_dir.mkdir(parents=True, exist_ok=True)
    record_path = record_dir / f"{manifest.snapshot_id}.json"
    record_path.write_text(json.dumps(asdict(manifest), ensure_ascii=False, indent=2), encoding="utf-8")
    return record_path


def load_snapshot_records(record_dir: Path | None) -> list[dict]:
    if record_dir is None or not record_dir.exists():
        return []
    records = []
    for path in sorted(record_dir.glob("*.json")):
        try:
            payload = json.loads(path.read_text(encoding="utf-8"))
        except (OSError, json.JSONDecodeError):
            continue
        if isinstance(payload, dict):
            payload.setdefault("record_path", path.as_posix())
            records.append(payload)
    return sorted(records, key=lambda item: (str(item.get("created_at", "")), str(item.get("snapshot_id", ""))))


def _path_text(path: Path | None) -> str:
    return path.as_posix() if path else ""


def _run_git(repo_root: Path, *args: str) -> str:
    del repo_root, args
    return ""


def _count_unique_doc_ids_from_chunks(path: Path | None) -> int:
    if path is None or not path.exists():
        return 0
    doc_ids: set[str] = set()
    with path.open("r", encoding="utf-8") as handle:
        for line in handle:
            if not line.strip():
                continue
            try:
                payload = json.loads(line)
            except json.JSONDecodeError:
                continue
            doc_id = payload.get("doc_id")
            if doc_id:
                doc_ids.add(str(doc_id))
    return len(doc_ids)


def _normalize_snapshot_kind(value: str) -> str:
    normalized = (value or "dev").strip().lower()
    if normalized not in ALLOWED_SNAPSHOT_KINDS:
        raise ValueError("snapshot_kind must be one of: dev, demo, internal, release")
    return normalized
