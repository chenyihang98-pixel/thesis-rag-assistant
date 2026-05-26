"""Section-aware chunking for thesis documents."""

from __future__ import annotations

from thesis_agent.models import DocumentSection, StructuredChunk, ThesisDocument
from thesis_agent.processing.sections import split_markdown_sections

HIGH_VALUE_SECTION_TYPES = {"abstract", "method", "experiment", "result", "conclusion"}
LOW_PRIORITY_SECTION_TYPES = {"references", "acknowledgement"}


def chunk_sections(
    sections: list[DocumentSection],
    doc_id: str,
    title: str,
    language: str = "ja",
    chunk_size: int = 700,
    overlap: int = 100,
) -> list[StructuredChunk]:
    """Split sections into overlapping structured chunks."""
    if not sections:
        return []
    if chunk_size <= 0:
        raise ValueError("chunk_size must be positive")
    if overlap < 0:
        raise ValueError("overlap must be non-negative")
    if overlap >= chunk_size:
        raise ValueError("overlap must be smaller than chunk_size")

    step = chunk_size - overlap
    chunks: list[StructuredChunk] = []
    global_index = 1
    for section_index, section in enumerate(sections, start=1):
        text = section.text.strip() or section.title
        start = 0
        local_index = 1
        while start < len(text):
            body = text[start : start + chunk_size].strip()
            if body:
                chunk_id = f"{doc_id}_s{section_index:03d}_chunk_{local_index:03d}"
                metadata = {
                    "doc_id": doc_id,
                    "title": title,
                    "chunk_index": global_index,
                    "section_title": section.title,
                    "section_type": section.section_type,
                    "heading_path": section.heading_path,
                    "page_start": section.page_start,
                    "page_end": section.page_end,
                    "is_high_value_for_embedding": section.section_type in HIGH_VALUE_SECTION_TYPES,
                    "is_low_priority_for_embedding": section.section_type in LOW_PRIORITY_SECTION_TYPES,
                }
                display_text = f"{section.title}\n{body}".strip()
                embedding_text = f"{title}\n{section.title}\n{body}".strip()
                chunks.append(
                    StructuredChunk(
                        chunk_id=chunk_id,
                        doc_id=doc_id,
                        title=title,
                        text=body,
                        embedding_text=embedding_text,
                        display_text=display_text,
                        language=language,
                        section_title=section.title,
                        section_type=section.section_type,
                        heading_path=section.heading_path,
                        page_start=section.page_start,
                        page_end=section.page_end,
                        chunk_index=global_index,
                        metadata=metadata,
                    )
                )
                global_index += 1
                local_index += 1
            start += step
    return chunks


def structured_chunk_document(
    document: ThesisDocument,
    language: str = "ja",
    chunk_size: int = 700,
    overlap: int = 100,
) -> list[StructuredChunk]:
    """Create structured chunks from a thesis document."""
    sections = split_markdown_sections(document.text, language=language)
    return chunk_sections(
        sections=sections,
        doc_id=document.doc_id,
        title=document.title,
        language=language,
        chunk_size=chunk_size,
        overlap=overlap,
    )
