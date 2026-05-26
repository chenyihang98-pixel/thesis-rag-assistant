"""Text cleanup helpers for model output."""

from __future__ import annotations

import re


def strip_reasoning_text(text: str) -> str:
    cleaned = re.sub(r"<think>.*?</think>", "", text or "", flags=re.IGNORECASE | re.DOTALL)
    cleaned = re.sub(r"(?im)^\s*(reasoning|chain of thought|思考|推理)\s*:\s*.*$", "", cleaned)
    return cleaned.strip()
