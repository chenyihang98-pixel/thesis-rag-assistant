"""Local Ollama /api/chat provider."""

from __future__ import annotations

import json
import urllib.error
import urllib.request
from dataclasses import dataclass

from thesis_agent.llm.providers import LLMMessage, LLMResponse


@dataclass
class OllamaProvider:
    model: str
    base_url: str = "http://localhost:11434"
    timeout_seconds: int = 90
    temperature: float = 0.2
    num_ctx: int = 2048
    num_predict: int | None = None
    keep_alive: str | None = None
    think: bool = False

    provider_name: str = "ollama"

    def generate(self, messages: list[LLMMessage]) -> LLMResponse:
        endpoint = self.base_url.rstrip("/") + "/api/chat"
        payload = {
            "model": self.model,
            "messages": [message.__dict__ for message in messages],
            "stream": False,
            "think": self.think,
            "options": {"temperature": self.temperature, "num_ctx": self.num_ctx},
        }
        if self.num_predict is not None:
            payload["options"]["num_predict"] = self.num_predict
        if self.keep_alive is not None:
            payload["keep_alive"] = self.keep_alive
        body = json.dumps(payload, ensure_ascii=False).encode("utf-8")
        request = urllib.request.Request(
            endpoint,
            data=body,
            headers={"Content-Type": "application/json; charset=utf-8"},
            method="POST",
        )
        try:
            with urllib.request.urlopen(request, timeout=self.timeout_seconds) as response:
                data = json.loads(response.read().decode("utf-8"))
        except (urllib.error.URLError, TimeoutError, json.JSONDecodeError) as exc:
            raise RuntimeError(f"Ollama request failed: {exc}") from exc
        message = data.get("message", {})
        return LLMResponse(
            content=message.get("content", ""),
            provider="ollama",
            model=self.model,
            metadata={
                "provider": "ollama",
                "model": self.model,
                "thinking": message.get("thinking", ""),
                "raw": {k: v for k, v in data.items() if k != "message"},
            },
        )
