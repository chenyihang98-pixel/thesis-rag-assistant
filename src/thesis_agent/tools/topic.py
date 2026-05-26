"""Topic similarity and local risk analysis helpers."""

from __future__ import annotations

from dataclasses import asdict
from pathlib import Path

from thesis_agent.privacy.pii import scan_pii
from thesis_agent.tools.schemas import ToolResult, TopicRiskAnalysis
from thesis_agent.tools.search import search_thesis


RISK_MEDIUM_THRESHOLD = 0.07
RISK_HIGH_THRESHOLD = 0.18


def risk_level_from_score(score: float) -> str:
    """Map a similarity score to the lightweight topic-risk level."""
    if score >= RISK_HIGH_THRESHOLD:
        return "high"
    if score >= RISK_MEDIUM_THRESHOLD:
        return "medium"
    return "low"


def _build_recommendations(risk_level: str, language: str = "ja") -> list[str]:
    """Return deterministic, localized topic-analysis recommendations."""
    recommendations = {
        "en": {
            "high": [
                "Clarify how the topic differs from existing work, especially scope, dataset, and evaluation criteria.",
                "The retrieved candidates overlap strongly, so consider adding a distinct use case or constraint.",
            ],
            "medium": [
                "List the overlapping points with related work and define comparison axes before narrowing the topic.",
                "You can improve originality by narrowing the purpose, target data, or evaluation perspective.",
            ],
            "low": [
                "The current overlap signal is low, but still document the difference from related work.",
                "Use the retrieved papers to make the target audience and application scenario more concrete.",
            ],
        },
        "zh": {
            "high": [
                "请明确本选题与已有研究的差异，尤其是研究范围、数据来源和评价条件。",
                "候选论文的重合信号较高，建议加入更明确的应用场景或约束条件。",
            ],
            "medium": [
                "请先整理与相关研究重合的论点，并定义比较维度。",
                "可以通过限定研究目的、目标数据或评价视角来提高独特性。",
            ],
            "low": [
                "当前重合信号不高，但仍建议继续明确与相关研究的差异。",
                "可参考检索结果，把目标读者和适用场景进一步具体化。",
            ],
        },
        "ja": {
            "high": [
                "既存研究との差分を明確にし、対象範囲・データ・評価条件を具体化してください。",
                "候補論文との重複シグナルが高いため、独自の利用場面や制約条件を追加することを検討してください。",
            ],
            "medium": [
                "関連研究と重なる論点を整理し、比較軸を先に定義してください。",
                "目的、対象データ、評価観点のいずれかを限定すると独自性を示しやすくなります。",
            ],
            "low": [
                "現時点では重複シグナルは高くありませんが、関連研究との差分は引き続き明文化してください。",
                "検索結果を参考に、対象読者や適用場面を具体化すると計画が安定します。",
            ],
        },
    }
    lang = language if language in recommendations else "ja"
    level = risk_level if risk_level in recommendations[lang] else "low"
    return recommendations[lang][level]


def compare_topic(
    index_path: Path,
    topic: str,
    top_k: int = 5,
    allow_pii_query: bool = False,
) -> ToolResult:
    """Compare a topic against retrieved synthetic thesis chunks."""
    if not topic or not topic.strip():
        return ToolResult(tool_name="compare_topic", ok=False, data={}, errors=["Topic must not be empty."])

    pii_findings = scan_pii(topic)
    if pii_findings and not allow_pii_query:
        return ToolResult(
            tool_name="compare_topic",
            ok=False,
            data={},
            errors=["PII detected in topic. Please remove personal or sensitive information before analysis."],
        )

    search_result = search_thesis(index_path=index_path, query=topic, top_k=top_k, allow_pii_query=allow_pii_query)
    if not search_result.ok:
        return ToolResult(tool_name="compare_topic", ok=False, data={}, errors=search_result.errors)

    results = search_result.data["results"]
    top_score = float(results[0]["score"]) if results else 0.0
    risk_level = risk_level_from_score(top_score)

    analysis = TopicRiskAnalysis(
        topic=topic,
        risk_level=risk_level,
        risk_score=round(top_score, 4),
        top_similarity_score=round(top_score, 4),
        similar_count=len(results),
        citations=[result["citation"] for result in results],
        recommendations=_build_recommendations(risk_level),
    )

    data = asdict(analysis)
    data["references"] = results
    data["note"] = "This is only a topic similarity / overlap signal, not plagiarism detection."
    return ToolResult(tool_name="compare_topic", ok=True, data=data)
