"""Embedding providers — local (sentence-transformers) or API."""

from typing import Protocol

import httpx

from app.config import settings
from app.services.cost_tracker import log_call

LOCAL_MODEL_NAME = "sentence-transformers/all-MiniLM-L6-v2"
OPENAI_EMBEDDING_MODEL = "text-embedding-3-small"


class EmbeddingProvider(Protocol):
    def embed(self, text: str) -> list[float]: ...

    def embed_many(self, texts: list[str]) -> list[list[float]]: ...


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
        return self.embed_many([text])[0]

    def embed_many(self, texts: list[str]) -> list[list[float]]:
        if not texts:
            return []
        model = self._load_model()
        vectors = model.encode(  # type: ignore[union-attr]
            texts,
            normalize_embeddings=True,
            show_progress_bar=False,
            batch_size=64,
        )
        log_call("local", self.model_name, len(texts))
        return [[float(x) for x in row.tolist()] for row in vectors]


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
        return self.embed_many([text])[0]

    def embed_many(self, texts: list[str]) -> list[list[float]]:
        if not texts:
            return []
        if not self.api_key:
            raise RuntimeError("OPENAI_API_KEY is not set")
        response = httpx.post(
            "https://api.openai.com/v1/embeddings",
            headers={"Authorization": f"Bearer {self.api_key}"},
            json={"model": self.model, "input": texts},
            timeout=30.0,
        )
        response.raise_for_status()
        rows = sorted(response.json()["data"], key=lambda item: item["index"])
        log_call("openai", self.model, len(texts))
        return [list(map(float, row["embedding"])) for row in rows]


_cached_provider: EmbeddingProvider | None = None


def get_embedding_provider() -> EmbeddingProvider:
    """Default is local (free). Set EMBEDDING_PROVIDER=openai to use the API.

    The provider is cached process-wide so SentenceTransformer is not reloaded
    on every Tier-2 lookup during a reconcile run.
    """
    global _cached_provider
    if _cached_provider is None:
        if settings.EMBEDDING_PROVIDER.lower() == "openai":
            _cached_provider = OpenAIEmbeddingProvider()
        else:
            _cached_provider = LocalSentenceTransformerProvider()
    return _cached_provider


def reset_embedding_provider() -> None:
    """Clear the cached provider (tests / config reload)."""
    global _cached_provider
    _cached_provider = None
