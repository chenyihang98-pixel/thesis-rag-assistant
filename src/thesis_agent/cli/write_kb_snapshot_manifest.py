"""CLI for writing a lightweight knowledge-base snapshot manifest."""

from __future__ import annotations

import argparse
from pathlib import Path

from thesis_agent.kb_snapshot import (
    ALLOWED_SNAPSHOT_KINDS,
    append_snapshot_history,
    build_kb_snapshot_manifest,
    resolve_snapshot_record_dir,
    resolve_snapshot_manifest_path,
    write_kb_snapshot_manifest,
    write_snapshot_record,
)


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Write a lightweight knowledge-base snapshot manifest.")
    parser.add_argument("--mode", choices=("demo", "internal"), default="demo")
    parser.add_argument("--snapshot-id", default="")
    parser.add_argument("--snapshot-kind", choices=sorted(ALLOWED_SNAPSHOT_KINDS), default="")
    parser.add_argument("--catalog-path", default="")
    parser.add_argument("--chunks-path", default="")
    parser.add_argument("--index-path", default="")
    parser.add_argument("--structured-chunks-path", default="")
    parser.add_argument("--structured-index-path", default="")
    parser.add_argument("--vector-path", default="")
    parser.add_argument("--embedding-provider", default="hash")
    parser.add_argument("--embedding-model", default="")
    parser.add_argument("--chunk-mode", default="")
    parser.add_argument("--notes", default="")
    parser.add_argument("--output", default="")
    parser.add_argument("--history-output", default="")
    parser.add_argument("--append-history", action=argparse.BooleanOptionalAction, default=True)
    parser.add_argument("--record-dir", default="")
    parser.add_argument("--write-record", action=argparse.BooleanOptionalAction, default=True)
    return parser


def main() -> None:
    parser = build_parser()
    args = parser.parse_args()
    output_path = Path(args.output) if args.output else resolve_snapshot_manifest_path(args.mode)
    if output_path is None:
        parser.error("internal mode requires --output or LAB_SNAPSHOT_MANIFEST_PATH")
    manifest = build_kb_snapshot_manifest(
        mode=args.mode,
        snapshot_id=args.snapshot_id or None,
        catalog_path=_optional_path(args.catalog_path),
        chunks_path=_optional_path(args.chunks_path),
        index_path=_optional_path(args.index_path),
        structured_chunks_path=_optional_path(args.structured_chunks_path),
        structured_index_path=_optional_path(args.structured_index_path),
        vector_path=_optional_path(args.vector_path),
        embedding_provider=args.embedding_provider,
        embedding_model=args.embedding_model,
        snapshot_kind=args.snapshot_kind or args.mode,
        chunk_mode=args.chunk_mode,
        notes=args.notes,
    )
    write_kb_snapshot_manifest(manifest, output_path)
    history_path = None
    if args.append_history:
        history_path = Path(args.history_output) if args.history_output else output_path.with_name("kb_snapshot_history.json")
        append_snapshot_history(manifest, history_path)
    record_path = None
    if args.write_record:
        record_dir = Path(args.record_dir) if args.record_dir else resolve_snapshot_record_dir(args.mode, output_path)
        if record_dir is not None:
            record_path = write_snapshot_record(manifest, record_dir)
    print(f"snapshot_id={manifest.snapshot_id}")
    print(f"snapshot_kind={manifest.snapshot_kind}")
    print(f"created_at={manifest.created_at}")
    print(f"document_count={manifest.document_count}")
    print(f"chunk_count={manifest.chunk_count}")
    print(f"output={output_path.as_posix()}")
    if history_path is not None:
        print(f"history={history_path.as_posix()}")
    if record_path is not None:
        print(f"record={record_path.as_posix()}")


def _optional_path(value: str) -> Path | None:
    stripped = (value or "").strip()
    return Path(stripped) if stripped else None


if __name__ == "__main__":
    main()
