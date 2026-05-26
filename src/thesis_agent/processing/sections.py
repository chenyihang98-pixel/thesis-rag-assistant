"""Section detection helpers for synthetic thesis documents."""

from __future__ import annotations

import re

from thesis_agent.models import DocumentSection


SECTION_KEYWORDS: dict[str, dict[str, list[str]]] = {
    "abstract": {
        "ja": ["要旨", "概要"],
        "zh": ["摘要", "概要"],
        "en": ["abstract", "summary"],
    },
    "keywords": {
        "ja": ["キーワード"],
        "zh": ["关键词", "关键字"],
        "en": ["keywords"],
    },
    "toc": {
        "ja": ["目次", "章構成"],
        "zh": ["目录", "章节概要"],
        "en": ["table of contents", "outline"],
    },
    "introduction": {
        "ja": ["序論", "はじめに"],
        "zh": ["绪论", "引言"],
        "en": ["introduction"],
    },
    "method": {
        "ja": ["手法", "提案手法", "方法"],
        "zh": ["方法", "研究方法"],
        "en": ["method", "methodology", "approach"],
    },
    "experiment": {
        "ja": ["実験", "評価"],
        "zh": ["实验", "评价", "评估"],
        "en": ["experiment", "evaluation"],
    },
    "result": {
        "ja": ["結果"],
        "zh": ["结果"],
        "en": ["result", "results"],
    },
    "discussion": {
        "ja": ["考察"],
        "zh": ["讨论"],
        "en": ["discussion"],
    },
    "conclusion": {
        "ja": ["結論", "おわりに"],
        "zh": ["结论", "总结"],
        "en": ["conclusion"],
    },
    "references": {
        "ja": ["参考文献"],
        "zh": ["参考文献"],
        "en": ["references", "bibliography"],
    },
    "acknowledgement": {
        "ja": ["謝辞"],
        "zh": ["致谢"],
        "en": ["acknowledgement", "acknowledgements"],
    },
    "title": {
        "ja": ["タイトル", "題目"],
        "zh": ["题目", "标题"],
        "en": ["title"],
    },
}

LABEL_PATTERN = re.compile(r"^\s*(#{1,6})\s+(.+?)\s*$")
COLON_PATTERN = re.compile(r"^\s*([^:：]{1,40})\s*[:：]\s*(.*)$")


def detect_section_type(title: str, text: str = "", language: str = "ja") -> str:
    """Classify a section title into a stable section type."""
    haystack = f"{title}\n{text[:80]}".strip().lower()
    if not haystack:
        return "unknown"
    for section_type, per_language in SECTION_KEYWORDS.items():
        keywords = per_language.get(language, []) + per_language.get("en", [])
        for keyword in keywords:
            if keyword.lower() in haystack:
                return section_type
    return "body"


def split_markdown_sections(text: str, language: str = "ja") -> list[DocumentSection]:
    """Split Markdown or label-style text into coarse document sections."""
    if not text or not text.strip():
        return []

    sections: list[DocumentSection] = []
    current_title = "Body"
    current_level = 1
    current_lines: list[str] = []
    heading_stack: list[tuple[int, str]] = []
    section_index = 1

    def flush() -> None:
        nonlocal section_index, current_lines
        body = "\n".join(current_lines).strip()
        if not body and current_title == "Body":
            return
        path = [title for _, title in heading_stack] or [current_title]
        section_type = detect_section_type(current_title, body, language=language)
        sections.append(
            DocumentSection(
                section_id=f"s{section_index:03d}",
                title=current_title,
                section_type=section_type,
                text=body,
                heading_path=path,
            )
        )
        section_index += 1
        current_lines = []

    for line in text.splitlines():
        heading_match = LABEL_PATTERN.match(line)
        colon_match = COLON_PATTERN.match(line)
        if heading_match:
            flush()
            current_level = len(heading_match.group(1))
            current_title = heading_match.group(2).strip()
            heading_stack = [(level, title) for level, title in heading_stack if level < current_level]
            heading_stack.append((current_level, current_title))
            continue
        if colon_match and detect_section_type(colon_match.group(1), language=language) != "body":
            flush()
            current_level = 1
            current_title = colon_match.group(1).strip()
            heading_stack = [(current_level, current_title)]
            remainder = colon_match.group(2).strip()
            if remainder:
                current_lines.append(remainder)
            continue
        current_lines.append(line)

    flush()
    if not sections:
        sections.append(
            DocumentSection(
                section_id="s001",
                title="Body",
                section_type="body",
                text=text.strip(),
                heading_path=["Body"],
            )
        )
    return sections
