"""Tier 1 — deterministic exact match on amount and date."""

from collections import defaultdict
from dataclasses import dataclass, field
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


@dataclass
class AmountIndex:
    """Reusable amount buckets so Tier 1 is O(B + L), not O(B × L)."""

    buckets: dict[int, list[MatchableTx]] = field(default_factory=lambda: defaultdict(list))
    by_id: dict[UUID, MatchableTx] = field(default_factory=dict)

    @classmethod
    def from_rows(cls, ledger_candidates: list[MatchableTx]) -> "AmountIndex":
        index = cls()
        for ledger_tx in ledger_candidates:
            index.by_id[ledger_tx.id] = ledger_tx
            index.buckets[_cent_key(ledger_tx.amount)].append(ledger_tx)
        return index

    def remove(self, tx_id: UUID) -> None:
        ledger_tx = self.by_id.pop(tx_id, None)
        if ledger_tx is None:
            return
        key = _cent_key(ledger_tx.amount)
        bucket = self.buckets.get(key)
        if not bucket:
            return
        self.buckets[key] = [row for row in bucket if row.id != tx_id]

    def match(
        self,
        bank_tx: MatchableTx,
        amount_tol: float = 0.01,
        date_window_days: int = 1,
    ) -> MatchResult:
        bank_amount = _as_float(bank_tx.amount)
        tol_cents = max(1, int(round(amount_tol * 100)))
        bank_cents = _cent_key(bank_tx.amount)
        nearby: list[MatchableTx] = []
        for offset in range(-tol_cents, tol_cents + 1):
            nearby.extend(self.buckets.get(bank_cents + offset, []))

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


def try_exact_match(
    bank_tx: MatchableTx,
    ledger_candidates: list[MatchableTx],
    amount_tol: float = 0.01,
    date_window_days: int = 1,
) -> MatchResult:
    """Match on amount (±tolerance) and date (±window).

    Prefer ``AmountIndex`` in multi-row reconcile loops so buckets are built once.
    """
    return AmountIndex.from_rows(ledger_candidates).match(
        bank_tx,
        amount_tol=amount_tol,
        date_window_days=date_window_days,
    )
