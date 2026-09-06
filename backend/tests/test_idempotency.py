"""Idempotency: re-running reconcile/run must not duplicate decisions."""

from datetime import date
from decimal import Decimal
from unittest.mock import MagicMock
from uuid import uuid4

from app.db.models import Transaction
from app.services.reconciliation_service import is_open_for_matching, run_reconciliation


def _tx(
    *,
    source: str,
    amount: str,
    status: str = "unmatched",
    description: str = "ACME",
) -> Transaction:
    return Transaction(
        id=uuid4(),
        source=source,
        date=date(2026, 9, 1),
        amount=Decimal(amount),
        currency="USD",
        description=description,
        counterparty="ACME",
        status=status,
    )


async def _quiet_agent(_tx: Transaction, _ctx: object) -> dict:
    return {
        "risk_score": 0.2,
        "risk_factors": [],
        "explanation": "Looks routine.",
    }


def test_resolved_statuses_are_not_open_for_matching() -> None:
    assert is_open_for_matching(_tx(source="bank", amount="10.00", status="unmatched"))
    assert not is_open_for_matching(_tx(source="bank", amount="10.00", status="matched"))
    assert not is_open_for_matching(_tx(source="bank", amount="10.00", status="flagged"))
    assert not is_open_for_matching(_tx(source="bank", amount="10.00", status="pending_review"))


def test_second_reconcile_run_does_not_add_decisions() -> None:
    """Same bank/ledger pair: first run writes one decision; second writes zero."""
    bank = _tx(source="bank", amount="100.00")
    ledger = _tx(source="ledger", amount="100.00")
    db = MagicMock()
    decisions: list[object] = []

    def _capture(row: object) -> None:
        decisions.append(row)

    db.add.side_effect = _capture
    db.get.side_effect = lambda _model, pk: ledger if pk == ledger.id else None

    first = run_reconciliation(
        db,
        bank_rows=[bank],
        ledger_rows=[ledger],
        skip_semantic=True,
        notify=False,
        score_fn=_quiet_agent,
    )
    assert first["exact_rule"] == 1
    assert first["decisions_written"] == 1
    assert bank.status == "matched"
    assert ledger.status == "matched"
    decision_count_after_first = len(decisions)

    second = run_reconciliation(
        db,
        bank_rows=[bank],
        ledger_rows=[ledger],
        skip_semantic=True,
        notify=False,
        score_fn=_quiet_agent,
    )
    assert second["processed"] == 0
    assert second["decisions_written"] == 0
    assert len(decisions) == decision_count_after_first
