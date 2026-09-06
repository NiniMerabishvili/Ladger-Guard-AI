"""Tests for Tier 1 deterministic matching."""

from dataclasses import dataclass
from datetime import date, timedelta
from uuid import uuid4

from app.matching.tier1_rules import try_exact_match


@dataclass
class FakeTx:
    id: object
    amount: float
    date: date


def _tx(amount: float, day: date | None = None) -> FakeTx:
    return FakeTx(id=uuid4(), amount=amount, date=day or date(2026, 9, 1))


def test_exact_match_identical_amount_and_date() -> None:
    bank = _tx(100.00)
    ledger = _tx(100.00)
    result = try_exact_match(bank, [ledger])
    assert result.matched is True
    assert result.confidence == 1.0
    assert result.method == "exact_rule"
    assert result.matched_id == ledger.id


def test_floating_point_tolerance_still_matches() -> None:
    bank = _tx(100.00)
    ledger = _tx(100.005)
    result = try_exact_match(bank, [ledger])
    assert result.matched is True
    assert result.matched_id == ledger.id


def test_date_window_plus_or_minus_one_day() -> None:
    bank = _tx(50.00, date(2026, 9, 2))
    plus_one = _tx(50.00, date(2026, 9, 3))
    minus_one = _tx(50.00, date(2026, 9, 1))
    assert try_exact_match(bank, [plus_one]).matched is True
    assert try_exact_match(bank, [minus_one]).matched is True


def test_amount_outside_tolerance_no_match() -> None:
    bank = _tx(100.00)
    ledger = _tx(100.02)
    result = try_exact_match(bank, [ledger])
    assert result.matched is False
    assert result.matched_id is None


def test_date_outside_window_no_match() -> None:
    bank = _tx(100.00, date(2026, 9, 1))
    ledger = _tx(100.00, date(2026, 9, 1) + timedelta(days=2))
    result = try_exact_match(bank, [ledger])
    assert result.matched is False
    assert result.matched_id is None

