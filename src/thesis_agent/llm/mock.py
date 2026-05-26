"""Deterministic local mock LLM."""

from __future__ import annotations

from thesis_agent.llm.providers import MockLLMProvider


class MockLLM:
    provider_name = "mock"

    _TOPIC_LABELS = {
        "en": {
            "title": "Topic Analysis Report",
            "topic": "Topic",
            "summary": "Summary",
            "summary_body": "This deterministic local report is generated from retrieved demo/internal runtime assets.",
            "similar": "Similar Papers",
            "none": "No similar papers found.",
            "risk": "Risk",
            "risk_level": "Risk Level",
            "risk_score": "Risk Score",
            "recommendations": "Recommendations",
            "fallback": "Refine the topic scope and compare with cited papers.",
            "structure": "Structure Check",
            "score": "Score",
            "citations": "Citations",
            "no_citations": "No citations available.",
        },
        "zh": {
            "title": "选题分析报告",
            "topic": "选题",
            "summary": "摘要",
            "summary_body": "本报告由本地 MockLLM 基于检索到的 demo/internal 运行资产生成。",
            "similar": "相似论文",
            "none": "未找到相似论文。",
            "risk": "风险",
            "risk_level": "风险等级",
            "risk_score": "风险分数",
            "recommendations": "建议",
            "fallback": "请缩小选题范围，并与引用论文逐项比较。",
            "structure": "结构检查",
            "score": "分数",
            "citations": "引用",
            "no_citations": "暂无引用。",
        },
        "ja": {
            "title": "選題分析レポート",
            "topic": "テーマ",
            "summary": "概要",
            "summary_body": "このレポートは、検索された demo/internal 実行資産に基づいてローカル MockLLM が生成したものです。",
            "similar": "類似論文",
            "none": "類似論文は見つかりませんでした。",
            "risk": "リスク",
            "risk_level": "リスクレベル",
            "risk_score": "リスクスコア",
            "recommendations": "推奨事項",
            "fallback": "テーマの範囲を絞り、引用論文と比較してください。",
            "structure": "構成チェック",
            "score": "スコア",
            "citations": "引用",
            "no_citations": "引用はありません。",
        },
    }

    def generate_topic_report(
        self,
        topic: str,
        topic_analysis: dict,
        search_results: list[dict],
        structure_analysis: dict | None = None,
        language: str = "ja",
    ) -> str:
        labels = self._TOPIC_LABELS.get(language, self._TOPIC_LABELS["ja"])
        citations = topic_analysis.get("citations", [])
        recommendations = topic_analysis.get("recommendations", [])
        lines = [
            f"# {labels['title']}",
            "",
            f"{labels['topic']}: {topic}",
            "",
            f"## {labels['summary']}",
            "",
            labels["summary_body"],
            "",
            f"## {labels['similar']}",
            "",
        ]
        for item in search_results:
            lines.append(f"- {item.get('title', 'Untitled')} ({item.get('citation', '')})")
        if not search_results:
            lines.append(f"- {labels['none']}")
        lines.extend(
            [
                "",
                f"## {labels['risk']}",
                "",
                f"- {labels['risk_level']}: {topic_analysis.get('risk_level', 'unknown')}",
                f"- {labels['risk_score']}: {float(topic_analysis.get('risk_score', 0.0)):.4f}",
                "",
                f"## {labels['recommendations']}",
                "",
            ]
        )
        lines.extend([f"- {item}" for item in recommendations] or [f"- {labels['fallback']}"])
        if structure_analysis:
            lines.extend(["", f"## {labels['structure']}", "", f"- {labels['score']}: {structure_analysis.get('score', 0.0)}"])
        lines.extend(["", f"## {labels['citations']}", ""])
        lines.extend([f"- {citation}" for citation in citations] or [f"- {labels['no_citations']}"])
        return "\n".join(lines)


__all__ = ["MockLLM", "MockLLMProvider"]
