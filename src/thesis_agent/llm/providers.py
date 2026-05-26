"""LLM provider interfaces."""

from __future__ import annotations

import re
from dataclasses import dataclass, field
from typing import Protocol


@dataclass
class LLMMessage:
    role: str
    content: str


@dataclass
class LLMResponse:
    content: str
    provider: str
    model: str | None = None
    metadata: dict = field(default_factory=dict)


class LLMProvider(Protocol):
    provider_name: str

    def generate(self, messages: list[LLMMessage]) -> LLMResponse:
        ...


class MockLLMProvider:
    """Deterministic local provider used by tests and default flows."""

    provider_name = "mock"

    def generate(self, messages: list[LLMMessage]) -> LLMResponse:
        prompt = "\n".join(message.content for message in messages)
        user_content = "\n".join(message.content for message in messages if message.role == "user")
        language = self._detect_language(prompt)
        question = self._extract_question(user_content)
        contexts = self._parse_retrieved_contexts(prompt)
        intent = self._detect_intent(question)
        if contexts:
            content = self._context_aware_answer(language=language, question=question, contexts=contexts, intent=intent)
        else:
            alias = self._first_available_alias(prompt)
            content = self._localized_answer(language=language, question=question, alias=alias)
        return LLMResponse(
            content=content,
            provider="mock",
            model="mock",
            metadata={
                "prompt_chars": len(user_content),
                "detected_language": language,
                "mock_intent": intent,
                "mock_context_count": len(contexts),
            },
        )

    @staticmethod
    def _detect_language(prompt: str) -> str:
        lowered = (prompt or "").lower()
        if re.search(r"(answer|target answer)\s+language\s*:\s*zh\b", lowered) or "language=zh" in lowered:
            return "zh"
        if "simplified chinese" in lowered or "必须使用简体中文" in prompt or "简体中文" in prompt:
            return "zh"
        if re.search(r"(answer|target answer)\s+language\s*:\s*en\b", lowered) or "language=en" in lowered:
            return "en"
        if "must answer in english" in lowered or "answer in english" in lowered or "rewrite the answer body in english" in lowered:
            return "en"
        if re.search(r"(answer|target answer)\s+language\s*:\s*ja\b", lowered) or "language=ja" in lowered:
            return "ja"
        if "日本語" in prompt or "japanese" in lowered:
            return "ja"
        return "zh"

    @staticmethod
    def _first_available_alias(prompt: str) -> str:
        registry_aliases = re.findall(r"(?m)^\s*-\s*(\[\d+\])\s+Citation:", prompt or "")
        if registry_aliases:
            return registry_aliases[0]
        context_aliases = re.findall(r"(?m)^\s*(\[\d+\])\s*$", prompt or "")
        if context_aliases:
            return context_aliases[0]
        aliases = sorted(set(re.findall(r"\[\d+\]", prompt or "")), key=lambda value: int(value.strip("[]")))
        return aliases[0] if aliases else ""

    @staticmethod
    def _extract_question(user_content: str) -> str:
        if "User question:" not in user_content:
            return ""
        lines = user_content.split("User question:", 1)[1].splitlines()
        for line in lines:
            stripped = line.strip()
            if stripped:
                return stripped
        return ""

    @staticmethod
    def _parse_retrieved_contexts(prompt: str) -> list[dict[str, str]]:
        lines = (prompt or "").splitlines()
        contexts: list[dict[str, str]] = []
        current: dict[str, str] | None = None
        in_contexts = False

        for raw_line in lines:
            line = raw_line.strip()
            if line.lower().startswith("retrieved contexts"):
                in_contexts = True
                continue
            if in_contexts and re.fullmatch(r"\[\d+\]", line):
                if current:
                    contexts.append(current)
                current = {"alias": line, "citation": "", "title": "", "snippet": ""}
                continue
            if not in_contexts or current is None:
                continue
            if line.startswith("Citation:"):
                current["citation"] = line.split("Citation:", 1)[1].strip()
            elif line.startswith("Title:"):
                current["title"] = line.split("Title:", 1)[1].strip()
            elif line.startswith("Snippet:"):
                current["snippet"] = line.split("Snippet:", 1)[1].strip()
            elif line.startswith("Section:"):
                current["section"] = line.split("Section:", 1)[1].strip()
            elif line and current.get("snippet"):
                current["snippet"] = (current["snippet"] + " " + line).strip()

        if current:
            contexts.append(current)

        if not contexts:
            for match in re.finditer(
                r"(?m)^\s*-\s*(?P<alias>\[\d+\])\s+Citation:\s*(?P<citation>.*?)\s+Title:\s*(?P<title>.*)$",
                prompt or "",
            ):
                contexts.append(
                    {
                        "alias": match.group("alias").strip(),
                        "citation": match.group("citation").strip(),
                        "title": match.group("title").strip(),
                        "snippet": "",
                    }
                )

        return contexts[:3]

    @staticmethod
    def _detect_intent(question: str) -> str:
        lowered = (question or "").lower()
        if any(token in question for token in ("区别", "差异", "不同", "比较", "違い", "比較")) or any(
            token in lowered for token in ("difference", "differences", "different", "compare", "comparison")
        ):
            return "comparison"
        if any(token in question for token in ("风险", "重叠", "避开", "已有研究", "リスク", "重複", "差分")) or any(
            token in lowered for token in ("risk", "overlap")
        ):
            return "risk"
        return "summary"

    @staticmethod
    def _compact_text(value: str, *, limit: int = 72) -> str:
        compact = re.sub(r"\s+", " ", (value or "").strip())
        if not compact:
            return ""
        if len(compact) <= limit:
            return compact
        return compact[: limit - 1].rstrip() + "..."

    @staticmethod
    def _has_cjk_or_kana(value: str) -> bool:
        return any("\u3040" <= char <= "\u30ff" or "\u3400" <= char <= "\u9fff" for char in value or "")

    @staticmethod
    def _has_kana(value: str) -> bool:
        return any("\u3040" <= char <= "\u30ff" for char in value or "")

    @classmethod
    def _context_label(cls, context: dict[str, str], *, language: str) -> str:
        title = context.get("title") or context.get("citation") or "Untitled"
        alias = context.get("alias", "")
        snippet = cls._compact_text(context.get("snippet", ""))
        if language == "en":
            if cls._has_cjk_or_kana(title):
                title = f"candidate paper {alias}".strip()
            if snippet and cls._has_cjk_or_kana(snippet):
                return f"{title}: the retrieved source-language snippet indicates this paper is relevant to the question"
            if snippet:
                return f"{title}: {snippet}"
            return f"{title}: no snippet was available in the prompt"
        if language == "ja":
            if snippet:
                return f"「{title}」は、プロンプト内の片段では「{snippet}」を示しています"
            return f"「{title}」は、タイトル情報のみが利用できます"
        if cls._has_kana(title):
            title = f"候选论文 {alias}".strip()
        if snippet and cls._has_kana(snippet):
            return f"《{title}》的检索片段来自源语言，显示该论文与当前问题相关"
        if snippet:
            return f"《{title}》的片段显示：“{snippet}”"
        return f"《{title}》目前只有标题信息可用"

    @staticmethod
    def _aliases(contexts: list[dict[str, str]]) -> str:
        return "".join(context.get("alias", "") for context in contexts if context.get("alias"))

    @classmethod
    def _context_aware_answer(
        cls,
        *,
        language: str,
        question: str,
        contexts: list[dict[str, str]],
        intent: str,
    ) -> str:
        if language == "en":
            return cls._context_aware_answer_en(question=question, contexts=contexts, intent=intent)
        if language == "ja":
            return cls._context_aware_answer_ja(question=question, contexts=contexts, intent=intent)
        return cls._context_aware_answer_zh(question=question, contexts=contexts, intent=intent)

    @classmethod
    def _context_aware_answer_zh(cls, *, question: str, contexts: list[dict[str, str]], intent: str) -> str:
        aliases = cls._aliases(contexts)
        lines = ["## 回答", ""]
        if intent == "comparison":
            for context in contexts:
                lines.append(f"- {context['alias']} {cls._context_label(context, language='zh')}。")
            lines.append(f"- 综合来看，这些候选的主要区别通常体现在研究对象、处理流程和应用场景上。{aliases}")
        elif intent == "risk":
            lines.extend(
                [
                    f"- 相关研究的潜在重叠点来自当前检索结果中相近的主题和方法表述。{aliases}",
                    f"- 可以区分的角度包括数据来源、应用场景、评价指标和使用者群体。{aliases}",
                    f"- 建议把问题进一步缩小为可验证的子主题，再逐篇对照候选论文的贡献边界。{aliases}",
                ]
            )
        else:
            lines.append(f"- 当前检索结果可以这样概括：")
            for context in contexts:
                lines.append(f"  - {context['alias']} {cls._context_label(context, language='zh')}。")
            lines.append(f"- 回答问题“{question}”时，应优先围绕这些已检索到的证据展开。{aliases}")
        lines.extend(
            [
                "",
                "## 不确定性",
                "",
                "- 这是本地 deterministic mock 输出，用于验证 RAG 流程和引用链路；如果需要更自然的分析，请切换到 Ollama 或 API。",
            ]
        )
        return "\n".join(lines)

    @classmethod
    def _context_aware_answer_en(cls, *, question: str, contexts: list[dict[str, str]], intent: str) -> str:
        aliases = cls._aliases(contexts)
        lines = ["## Answer", ""]
        if intent == "comparison":
            for context in contexts:
                lines.append(f"- {context['alias']} focuses on {cls._context_label(context, language='en')}.")
            lines.append(
                f"- Overall, the main differences are likely in research objects, methods, and application settings. {aliases}"
            )
        elif intent == "risk":
            lines.extend(
                [
                    f"- Potential overlap comes from similar topics or methods in the retrieved candidates. {aliases}",
                    f"- Useful differentiation angles include data source, application setting, evaluation criteria, and user group. {aliases}",
                    f"- Narrow the topic into a verifiable sub-question and compare each candidate's contribution boundary. {aliases}",
                ]
            )
        else:
            lines.append("- The retrieved contexts suggest the following grounded summary:")
            for context in contexts:
                lines.append(f"  - {context['alias']} {cls._context_label(context, language='en')}.")
            lines.append(f"- For the question '{question}', the answer should stay close to these retrieved sources. {aliases}")
        lines.extend(
            [
                "",
                "## Uncertainty",
                "",
                "- This is a deterministic local mock output for testing RAG flow and citations; use Ollama or API for more natural analysis.",
            ]
        )
        return "\n".join(lines)

    @classmethod
    def _context_aware_answer_ja(cls, *, question: str, contexts: list[dict[str, str]], intent: str) -> str:
        aliases = cls._aliases(contexts)
        lines = ["## 回答", ""]
        if intent == "comparison":
            for context in contexts:
                lines.append(f"- {context['alias']} {cls._context_label(context, language='ja')}。")
            lines.append(f"- 全体として、違いは研究対象、手法、利用場面に現れやすいです。{aliases}")
        elif intent == "risk":
            lines.extend(
                [
                    f"- 既存研究との重複リスクは、検索結果内の近いテーマや方法にあります。{aliases}",
                    f"- 差分化するには、データ、利用場面、評価指標、対象ユーザーを明確に分けるとよいです。{aliases}",
                    f"- テーマを検証可能な小さい問いに絞り、各候補論文の貢献範囲と比較してください。{aliases}",
                ]
            )
        else:
            lines.append("- 現在の検索結果は次のように整理できます。")
            for context in contexts:
                lines.append(f"  - {context['alias']} {cls._context_label(context, language='ja')}。")
            lines.append(f"- 質問「{question}」に答える際は、これらの取得済み根拠から外れないことが重要です。{aliases}")
        lines.extend(
            [
                "",
                "## 不確実性",
                "",
                "- これは RAG の流れと引用を確認するためのローカル deterministic mock 出力です。自然な分析が必要な場合は Ollama または API を使用してください。",
            ]
        )
        return "\n".join(lines)

    @staticmethod
    def _localized_answer(*, language: str, question: str, alias: str) -> str:
        if language == "en":
            evidence = f" The main evidence comes from the current retrieved result {alias}." if alias else ""
            return (
                "## Answer\n\n"
                "This is a deterministic local MockLLM answer grounded in the retrieved context. "
                f"Question: {question}.{evidence}\n\n"
                "## Uncertainty\n\n"
                "- This is a local mock output and does not represent a real model judgment."
            )
        if language == "ja":
            evidence = f"主な根拠は現在の検索結果 {alias} です。" if alias else "利用可能な引用はありません。"
            return (
                "## 回答\n\n"
                f"これは取得された文脈に基づくローカル MockLLM の回答です。質問: {question}。{evidence}\n\n"
                "## 不確実性\n\n"
                "- これはローカル mock 出力であり、実際のモデル判断ではありません。"
            )
        evidence = f"主要依据来自当前检索结果 {alias}。" if alias else "当前没有可用引用。"
        return (
            "## 回答\n\n"
            f"这是基于检索上下文的本地 MockLLM 回答。问题：{question}。{evidence}\n\n"
            "## 不确定性\n\n"
            "- 这是本地 mock 输出，不代表真实模型判断。"
        )
