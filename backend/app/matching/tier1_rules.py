"""Tier 1 — deterministic exact match on amount and date."""

from collections import defaultdict
from dataclasses import dataclass
from datetime import date
from typing import Protocol
from uuid import UUID


class MatchableTx(Protocol):
    id: UUID
    amount: object
    date: date


@dataclass
class MatchResult:
    matched: bool
    confidence: float = 0.0
    method: str | None = None
    matched_id: UUID | None = None


def _as_float(amount: object) -> float:
    return float(amount)  # type: ignore[arg-type]


def _cent_key(amount: object) -> int:
    """Bucket by rounded cents so nearby amounts can be looked up quickly."""
    return int(round(_as_float(amount) * 100))


def try_exact_match(
    bank_tx: MatchableTx,
    ledger_candidates: list[MatchableTx],
    amount_tol: float = 0.01,
    date_window_days: int = 1,
) -> MatchResult:
    """Match on amount (±tolerance) and date (±window).

    Ledger rows are indexed by rounded amount so this stays cheap past ~1,000 rows.
    """
    buckets: dict[int, list[MatchableTx]] = defaultdict(list)
    for ledger_tx in ledger_candidates:
        buckets[_cent_key(ledger_tx.amount)].append(ledger_tx)

    bank_amount = _as_float(bank_tx.amount)
    tol_cents = max(1, int(round(amount_tol * 100)))
    nearby: list[MatchableTx] = []
    bank_cents = _cent_key(bank_tx.amount)
    for offset in range(-tol_cents, tol_cents + 1):
        nearby.extend(buckets.get(bank_cents + offset, []))

    for ledger_tx in nearby:
        same_amount = abs(bank_amount - _as_float(ledger_tx.amount)) <= amount_tol
        same_date = abs((bank_tx.date - ledger_tx.date).days) <= date_window_days
        if same_amount and same_date:
            return MatchResult(
                matched=True,
                confidence=1.0,
                method="exact_rule",
                matched_id=ledger_tx.id,
            )
    return MatchResult(matched=False)
