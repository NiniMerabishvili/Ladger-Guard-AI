"""Tests for Tier 2 semantic matching (mocked embeddings)."""

from dataclasses import dataclass
from datetime import date, timedelta
from uuid import uuid4

from app.matching.tier2_semantic import (
    SemanticCandidate,
    decide_semantic_match,
    opposite_source,
)


@dataclass
class FakeTx:
    id: object
    amount: float
    date: date
    description: str = "STARBUCKS STORE 11847"
    source: str = "bank"


class FixedEmbeddingProvider:
    """Maps known texts to fixed vectors — no model or API calls."""

    def __init__(self) -> None:
        self.vectors = {
            "STARBUCKS STORE 11847": [1.0, 0.0, 0.0],
            "Staff coffee Starbucks": [0.99, 0.01, 0.0],
            "UBER TRIP 9981": [0.0, 1.0, 0.0],
        }

    def embed(self, text: str) -> list[float]:
        return self.vectors[text]


def _candidate(*, similarity: float, amount: float = 4.50, days_off: int = 0) -> SemanticCandidate:
    return SemanticCandidate(
        id=uuid4(),
        description="Staff coffee Starbucks",
        amount=amount,
        date=date(2026, 9, 1) + timedelta(days=days_off),
        similarity=similarity,
    )


def test_semantic_match_above_threshold_and_close_amount_date() -> None:
    bank = FakeTx(id=uuid4(), amount=4.50, date=date(2026, 9, 1))
    result = decide_semantic_match(bank, [_candidate(similarity=0.92, days_off=2)])
    assert result.matched is True
    assert result.method == "semantic_match"
    assert result.confidence == 0.92


def test_semantic_match_below_similarity_threshold() -> None:
    bank = FakeTx(id=uuid4(), amount=4.50, date=date(2026, 9, 1))
    result = decide_semantic_match(bank, [_candidate(similarity=0.85)])
    assert result.matched is False


def test_semantic_match_amount_outside_wider_tolerance() -> None:
    bank = FakeTx(id=uuid4(), amount=100.00, date=date(2026, 9, 1))
    # 5% off — wider Tier 2 window is ±3%
    result = decide_semantic_match(bank, [_candidate(similarity=0.95, amount=105.00)])
    assert result.matched is False


def test_semantic_match_date_outside_wider_window() -> None:
    bank = FakeTx(id=uuid4(), amount=4.50, date=date(2026, 9, 1))
    result = decide_semantic_match(bank, [_candidate(similarity=0.95, days_off=4)])
    assert result.matched is False


def test_mocked_embedding_provider_returns_fixed_vectors() -> None:
    provider = FixedEmbeddingProvider()
    assert provider.embed("STARBUCKS STORE 11847") == [1.0, 0.0, 0.0]
    assert provider.embed("UBER TRIP 9981") == [0.0, 1.0, 0.0]


def test_opposite_source() -> None:
    assert opposite_source("bank") == "ledger"
    assert opposite_source("ledger") == "bank"
