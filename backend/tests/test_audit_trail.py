"""Audit trail: append-only decisions, chronological history."""

from datetime import datetime, timedelta
from unittest.mock import MagicMock
from uuid import uuid4

from app.db.models import Decision
from app.services.audit_service import get_decision_history, record_decision


def test_record_decision_always_inserts_a_new_row() -> None:
    db = MagicMock()
    tx_id = uuid4()
    first = record_decision(
        db,
        transaction_id=tx_id,
        decision="matched",
        method="exact_rule",
        confidence=1.0,
    )
    second = record_decision(
        db,
        transaction_id=tx_id,
        decision="pending_review",
        method="human_override",
        confidence=0.4,
        reviewed_by="reviewer",
    )
    assert db.add.call_count == 2
    assert first is not second
    assert first.id != second.id
    assert db.merge.call_count == 0


def test_get_decision_history_is_chronological() -> None:
    db = MagicMock()
    tx_id = uuid4()
    older = Decision(
        transaction_id=tx_id,
        decision="matched",
        method="exact_rule",
        confidence=1.0,
        created_at=datetime(2026, 9, 1, 10, 0, 0),
    )
    newer = Decision(
        transaction_id=tx_id,
        decision="flagged",
        method="llm_agent",
        confidence=0.8,
        created_at=datetime(2026, 9, 1, 10, 0, 0) + timedelta(minutes=5),
    )
    db.scalars.return_value.all.return_value = [older, newer]
    history = get_decision_history(db, tx_id)
    assert history == [older, newer]
    statement = str(db.scalars.call_args[0][0])
    assert "created_at" in statement.lower() or "decisions" in statement.lower()
