"""Tests for the review confidence threshold."""

from app.config import settings
from app.services.review_service import apply_review_threshold


def test_below_threshold_is_always_pending_review() -> None:
    assert settings.REVIEW_CONFIDENCE_THRESHOLD == 0.7
    assert apply_review_threshold(0.69, intended="matched") == "pending_review"
    assert apply_review_threshold(0.0, intended="matched") == "pending_review"


def test_at_or_above_threshold_keeps_intended_matched() -> None:
    assert apply_review_threshold(0.7, intended="matched") == "matched"
    assert apply_review_threshold(1.0, intended="matched") == "matched"
