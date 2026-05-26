"""Runtime citation aliases and canonicalization."""

from __future__ import annotations

import re
from dataclasses import dataclass, field
from pathlib import PureWindowsPath


@dataclass
class CitationRegistryEntry:
    alias: str
    citation: str
    title: str = ""
    doc_id: str = ""
    chunk_id: str = ""
    metadata: dict = field(default_factory=dict)


@dataclass
class CitationValidationResult:
    canonical_citations: list[str]
    direct_citations: list[str]
    alias_citations: list[str]
    resolved_aliases: dict[str, str]
    hallucinated_citations: list[str]
    unknown_aliases: list[str]
    missing_citation: bool
    citation_appendix_added: bool = False
    warnings: list[str] = field(default_factory=list)


def _looks_like_absolute_path(value: str) -> bool:
    stripped = value.strip()
    return bool(re.match(r"^[A-Za-z]:[\\/]", stripped) or stripped.startswith("/") or stripped.startswith("\\\\"))


def _safe_citation(value: str, *, doc_id: str, chunk_id: str, fallback: str) -> str:
    if value and not _looks_like_absolute_path(value):
        # A citation should be an opaque id, not a file path. If a path-like value sneaks in,
        # prefer the doc/chunk canonical id.
        name = PureWindowsPath(value).name
        if name != value and "#" not in value:
            return f"{doc_id}#{chunk_id}" if doc_id and chunk_id else fallback
        return value
    if doc_id and chunk_id:
        return f"{doc_id}#{chunk_id}"
    return fallback


def build_citation_registry(retrieved_contexts: list[dict]) -> list[CitationRegistryEntry]:
    registry: list[CitationRegistryEntry] = []
    for index, context in enumerate(retrieved_contexts, start=1):
        metadata = dict(context.get("metadata") or {})
        doc_id = str(context.get("doc_id") or metadata.get("doc_id") or "")
        chunk_id = str(context.get("chunk_id") or metadata.get("chunk_id") or "")
        citation = str(context.get("citation") or metadata.get("citation") or "")
        citation = _safe_citation(citation, doc_id=doc_id, chunk_id=chunk_id, fallback=f"context_{index}")
        registry.append(
            CitationRegistryEntry(
                alias=f"[{index}]",
                citation=citation,
                title=str(context.get("title") or metadata.get("title") or ""),
                doc_id=doc_id,
                chunk_id=chunk_id,
                metadata=metadata,
            )
        )
    return registry


def format_citation_registry_for_prompt(registry: list[CitationRegistryEntry]) -> str:
    lines = []
    for entry in registry:
        lines.append(f"- {entry.alias} Citation: {entry.citation} Title: {entry.title}")
    lines.append("Use only these aliases or canonical citations. Do not invent citations.")
    return "\n".join(lines)


def extract_direct_canonical_citations(answer: str, allowed_citations: set[str]) -> list[str]:
    return sorted(citation for citation in allowed_citations if citation and citation in (answer or ""))


def extract_numbered_aliases(answer: str) -> list[str]:
    return sorted(set(re.findall(r"\[\d+\]", answer or "")), key=lambda value: int(value.strip("[]")))


def get_reference_section_title(language: str = "zh") -> str:
    """Return the system-managed reference section heading for an answer language."""
    normalized = (language or "zh").lower()
    if normalized == "en":
        return "References"
    if normalized == "ja":
        return "参考文献"
    return "参考依据"


def get_citation_section_title(language: str = "zh") -> str:
    """Return a localized generic citation heading."""
    normalized = (language or "zh").lower()
    if normalized == "en":
        return "Citations"
    if normalized == "ja":
        return "引用"
    return "引用"


def _has_reference_section(answer: str) -> bool:
    lowered = answer.lower()
    return any(
        heading in lowered
        for heading in (
            "## 参考依据",
            "## 参考文献",
            "## references",
            "## reference",
        )
    )


def _extract_citation_like_strings(answer: str) -> list[str]:
    return sorted(set(re.findall(r"\b[\w.-]+#[\w.-]+\b", answer or "")))


def canonicalize_answer_citations(
    answer: str,
    registry: list[CitationRegistryEntry],
    *,
    append_reference_section: bool = True,
    language: str = "zh",
) -> tuple[str, CitationValidationResult]:
    allowed = {entry.citation for entry in registry}
    alias_map = {entry.alias: entry.citation for entry in registry}
    aliases = extract_numbered_aliases(answer)
    resolved = {alias: alias_map[alias] for alias in aliases if alias in alias_map}
    unknown_aliases = [alias for alias in aliases if alias not in alias_map]
    direct = extract_direct_canonical_citations(answer, allowed)
    citation_like = _extract_citation_like_strings(answer)
    hallucinated = [citation for citation in citation_like if citation not in allowed]
    canonical = sorted(set(direct + list(resolved.values())))
    missing = not canonical
    appendix_added = False
    final_answer = answer or ""
    if append_reference_section and registry and not _has_reference_section(final_answer):
        lines = ["", f"## {get_reference_section_title(language)}"]
        for entry in registry:
            lines.append(f"{entry.alias} {entry.title or entry.doc_id or 'Untitled'}")
            lines.append(f"{get_citation_section_title(language)}: {entry.citation}")
        final_answer = final_answer.rstrip() + "\n" + "\n".join(lines)
        appendix_added = True
    result = CitationValidationResult(
        canonical_citations=canonical,
        direct_citations=direct,
        alias_citations=[alias for alias in aliases if alias in alias_map],
        resolved_aliases=resolved,
        hallucinated_citations=hallucinated,
        unknown_aliases=unknown_aliases,
        missing_citation=missing,
        citation_appendix_added=appendix_added,
    )
    return final_answer, result


def validate_answer_citations(answer: str, registry: list[CitationRegistryEntry]) -> CitationValidationResult:
    return canonicalize_answer_citations(answer, registry, append_reference_section=False)[1]
