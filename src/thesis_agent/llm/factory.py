"""LLM provider factory."""

from __future__ import annotations

from thesis_agent.llm.api_compatible import ApiCompatibleProvider
from thesis_agent.llm.ollama import OllamaProvider
from thesis_agent.llm.providers import LLMProvider, MockLLMProvider


def get_llm_provider(name: str = "mock", **kwargs) -> LLMProvider:
    normalized = (name or "mock").strip().lower()
    if normalized == "mock":
        return MockLLMProvider()
    if normalized == "ollama":
        model = kwargs.get("model") or kwargs.get("ollama_model")
        if not model:
            raise ValueError(
                "Ollama model is not configured. Pass --ollama-model, set OLLAMA_MODEL, "
                "or run scripts/configure_llm.ps1."
            )
        return OllamaProvider(
            model=model,
            base_url=kwargs.get("base_url") or kwargs.get("ollama_base_url", "http://localhost:11434"),
            timeout_seconds=int(kwargs.get("timeout_seconds") or kwargs.get("ollama_timeout_seconds", 90)),
            temperature=float(kwargs.get("temperature") or kwargs.get("ollama_temperature", 0.2)),
            num_ctx=int(kwargs.get("num_ctx") or kwargs.get("ollama_num_ctx", 2048)),
            num_predict=kwargs.get("num_predict") or kwargs.get("ollama_num_predict"),
            think=bool(kwargs.get("think") or kwargs.get("ollama_think", False)),
        )
    if normalized == "api":
        return ApiCompatibleProvider(
            base_url=kwargs.get("api_base_url") or kwargs.get("base_url") or "",
            model=kwargs.get("api_model") or kwargs.get("model") or "",
            api_key=kwargs.get("api_key"),
            timeout_seconds=int(kwargs.get("api_timeout_seconds", 90)),
            temperature=float(kwargs.get("api_temperature", 0.2)),
            max_tokens=int(kwargs.get("api_max_tokens", 1200)),
        )
    raise ValueError(f"Unsupported LLM provider: {name}")
