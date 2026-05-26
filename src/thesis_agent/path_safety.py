"""Shared path allowlist helpers for local runtime assets."""

from __future__ import annotations

import os
from pathlib import Path


LAB_EXTERNAL_ASSET_ENV_VARS = {
    "LAB_PDF_ROOT",
    "LAB_CATALOG_PATH",
    "LAB_CHUNKS_PATH",
    "LAB_INDEX_PATH",
    "LAB_STRUCTURED_CHUNKS_PATH",
    "LAB_STRUCTURED_INDEX_PATH",
    "LAB_VECTOR_PATH",
    "LAB_SNAPSHOT_MANIFEST_PATH",
    "LAB_SNAPSHOT_HISTORY_PATH",
    "LAB_SNAPSHOT_RECORD_DIR",
}


def get_configured_external_asset_paths_from_env() -> set[Path]:
    paths: set[Path] = set()
    for name in LAB_EXTERNAL_ASSET_ENV_VARS:
        value = os.getenv(name, "").strip()
        if value:
            paths.add(Path(value).resolve())
    return paths


def is_allowed_external_asset_path(path: Path, allowed_paths: set[Path]) -> bool:
    resolved = path.resolve()
    for allowed in allowed_paths:
        if resolved == allowed:
            return True
        if allowed.exists() and allowed.is_dir():
            try:
                resolved.relative_to(allowed)
                return True
            except ValueError:
                pass
    return False
