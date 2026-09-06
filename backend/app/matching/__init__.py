"""Two-tier matching: deterministic rules and semantic embeddings."""

from app.matching.embedding_provider import (
    EmbeddingProvider,
    LocalSentenceTransformerProvider,
    OpenAIEmbeddingProvider,
    get_embedding_provider,
)
from app.matching.tier1_rules import MatchResult, try_exact_match
from app.matching.tier2_semantic import decide_semantic_match, try_semantic_match

__all__ = [
    "EmbeddingProvider",
    "LocalSentenceTransformerProvider",
    "MatchResult",
    "OpenAIEmbeddingProvider",
    "decide_semantic_match",
    "get_embedding_provider",
    "try_exact_match",
    "try_semantic_match",
]
