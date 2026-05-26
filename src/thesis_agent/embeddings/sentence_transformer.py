"""Optional sentence-transformer embedding provider.

The dependency is declared for manual semantic experiments, but tests should
use the hash provider unless they explicitly monkeypatch the model loader.
"""

from __future__ import annotations


class SentenceTransformerEmbeddingProvider:
    provider_name = "sentence-transformer"

    def __init__(self, model_name: str = "sentence-transformers/paraphrase-multilingual-MiniLM-L12-v2") -> None:
        self.model_name = model_name
        try:
            from sentence_transformers import SentenceTransformer
        except Exception as exc:  # pragma: no cover - depends on optional runtime package state
            raise RuntimeError("sentence-transformers is not available in this environment") from exc
        self._model = SentenceTransformer(model_name)

    def embed_text(self, text: str) -> list[float]:
        return [float(value) for value in self._model.encode([text], normalize_embeddings=True)[0]]

    def embed_texts(self, texts: list[str]) -> list[list[float]]:
        vectors = self._model.encode(texts, normalize_embeddings=True)
        return [[float(value) for value in vector] for vector in vectors]
