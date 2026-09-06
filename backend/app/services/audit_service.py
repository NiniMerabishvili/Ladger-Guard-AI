"""Write-only audit trail — every decision is a new row, never overwritten."""

from datetime import datetime, timezone
from uuid import UUID, uuid4

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.db.models import Decision


def record_decision(
    db: Session,
    *,
    transaction_id: UUID,
    decision: str,
    method: str,
    confidence: float,
    matched_transaction_id: UUID | None = None,
    reasoning: dict | None = None,
    model_used: str | None = None,
    reviewed_by: str | None = None,
    matching_run_id: UUID | None = None,
    flush: bool = True,
) -> Decision:
    """Insert a new decisions row. Existing rows are never updated.

    Pass ``flush=False`` during batch reconcile so many decisions share one flush.
    """
    row = Decision(
        id=uuid4(),
        transaction_id=transaction_id,
        matched_transaction_id=matched_transaction_id,
        decision=decision,
        method=method,
        confidence=confidence,
        reasoning=reasoning,
        model_used=model_used,
        reviewed_by=reviewed_by,
        matching_run_id=matching_run_id,
        created_at=datetime.now(timezone.utc).replace(tzinfo=None),
    )
    db.add(row)
    if flush:
        db.flush()
    return row


def get_decision_history(db: Session, transaction_id: UUID) -> list[Decision]:
    """Every decision for a transaction, oldest first."""
    return list(
        db.scalars(
            select(Decision)
            .where(Decision.transaction_id == transaction_id)
            .order_by(Decision.created_at.asc(), Decision.id.asc())
        ).all()
    )
