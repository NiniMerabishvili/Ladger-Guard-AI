"""Embedding providers — local (sentence-transformers) or API."""

from typing import Protocol

import httpx

from app.config import settings
from app.services.cost_tracker import log_call

LOCAL_MODEL_NAME = "sentence-transformers/all-MiniLM-L6-v2"
OPENAI_EMBEDDING_MODEL = "text-embedding-3-small"


class EmbeddingProvider(Protocol):
    def embed(self, text: str) -> list[float]: ...


class LocalSentenceTransformerProvider:
    """sentence-transformers/all-MiniLM-L6-v2 — free, fast, 384-dim."""

    def __init__(self, model_name: str = LOCAL_MODEL_NAME) -> None:
        self.model_name = model_name
        self._model: object | None = None

    def _load_model(self) -> object:
        if self._model is None:
            from sentence_transformers import SentenceTransformer

            self._model = SentenceTransformer(self.model_name)
        return self._model

    def embed(self, text: str) -> list[float]:
        model = self._load_model()
        vector = model.encode(text, normalize_embeddings=True)  # type: ignore[union-attr]
        log_call("local", self.model_name, 1)
        return [float(x) for x in vector.tolist()]


class OpenAIEmbeddingProvider:
    """text-embedding-3-small, for fallback/comparison.

    Note: this model is 1536-dim; the DB column is VECTOR(384) for the local model.
    """

    def __init__(
        self,
        api_key: str | None = None,
        model: str = OPENAI_EMBEDDING_MODEL,
    ) -> None:
        self.api_key = api_key if api_key is not None else settings.OPENAI_API_KEY
        self.model = model

    def embed(self, text: str) -> list[float]:
        if not self.api_key:
            raise RuntimeError("OPENAI_API_KEY is not set")
        response = httpx.post(
            "https://api.openai.com/v1/embeddings",
            headers={"Authorization": f"Bearer {self.api_key}"},
            json={"model": self.model, "input": text},
            timeout=30.0,
        )
        response.raise_for_status()
        payload: list[float] = response.json()["data"][0]["embedding"]
        log_call("openai", self.model, 1)
        return payload


def get_embedding_provider() -> EmbeddingProvider:
    """Default is local (free). Set EMBEDDING_PROVIDER=openai to use the API."""
    if settings.EMBEDDING_PROVIDER.lower() == "openai":
        return OpenAIEmbeddingProvider()
    return LocalSentenceTransformerProvider()
