"""本地论文处理流程使用的轻量数据结构。"""

from __future__ import annotations

from dataclasses import dataclass, field


@dataclass(frozen=True)
class ThesisDocument:
    """Structured representation of one synthetic thesis sample."""

    doc_id: str
    title: str
    abstract: str
    keywords: list[str]
    year: str
    major: str
    source_type: str
    source_name: str
    document_language: str
    text: str
    author_name: str = ""
    student_id: str = ""
    advisor_name: str = ""
    original_filename: str = ""
    pdf_path: str = ""


@dataclass(frozen=True)
class ThesisChunk:
    """Character-based chunk for downstream local processing."""

    chunk_id: str
    doc_id: str
    title: str
    text: str
    metadata: dict = field(default_factory=dict)


@dataclass(frozen=True)
class DocumentPage:
    """One text-extracted document page."""

    page_number: int
    text: str


@dataclass(frozen=True)
class DocumentSection:
    """Section-level representation used by structured chunking."""

    section_id: str
    title: str
    section_type: str
    text: str
    page_start: int | None = None
    page_end: int | None = None
    heading_path: list[str] = field(default_factory=list)


@dataclass(frozen=True)
class StructuredChunk:
    """Section-aware chunk prepared for retrieval and future embeddings."""

    chunk_id: str
    doc_id: str
    title: str
    text: str
    embedding_text: str
    display_text: str
    language: str = "ja"
    section_title: str = ""
    section_type: str = "body"
    heading_path: list[str] = field(default_factory=list)
    page_start: int | None = None
    page_end: int | None = None
    chunk_index: int = 0
    metadata: dict = field(default_factory=dict)
