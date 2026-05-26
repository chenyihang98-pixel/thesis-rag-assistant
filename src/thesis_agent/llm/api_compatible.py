"""OpenAI-compatible chat completions provider shell."""

from __future__ import annotations

import json
import urllib.error
import urllib.request
from dataclasses import dataclass

from thesis_agent.llm.providers import LLMMessage, LLMResponse


@dataclass
class ApiCompatibleProvider:
    base_url: str
    model: str
    api_key: str | None = None
    timeout_seconds: int = 90
    temperature: float = 0.2
    max_tokens: int = 1200

    provider_name: str = "api"

    def generate(self, messages: list[LLMMessage]) -> LLMResponse:
        if not self.base_url:
            raise RuntimeError("API base_url is required")
        if not self.model:
            raise RuntimeError("API model is required")
        endpoint = _chat_completions_endpoint(self.base_url)
        payload = {
            "model": self.model,
            "messages": [message.__dict__ for message in messages],
            "temperature": self.temperature,
            "max_tokens": self.max_tokens,
            "stream": False,
        }
        headers = {"Content-Type": "application/json; charset=utf-8"}
        if self.api_key:
            headers["Authorization"] = f"Bearer {self.api_key}"
        request = urllib.request.Request(
            endpoint,
            data=json.dumps(payload, ensure_ascii=False).encode("utf-8"),
            headers=headers,
            method="POST",
        )
        try:
            with urllib.request.urlopen(request, timeout=self.timeout_seconds) as response:
                data = json.loads(response.read().decode("utf-8"))
        except (urllib.error.URLError, TimeoutError, json.JSONDecodeError) as exc:
            raise RuntimeError(f"API-compatible request failed: {exc}") from exc
        try:
            content = data["choices"][0]["message"]["content"]
        except (KeyError, IndexError, TypeError) as exc:
            raise RuntimeError("API-compatible response did not contain choices[0].message.content") from exc
        return LLMResponse(content=content, provider="api", model=self.model, metadata={"endpoint": endpoint})


def _chat_completions_endpoint(base_url: str) -> str:
    stripped = base_url.rstrip("/")
    if stripped.endswith("/chat/completions"):
        return stripped
    if stripped.endswith("/v1"):
        return stripped + "/chat/completions"
    return stripped + "/v1/chat/completions"
