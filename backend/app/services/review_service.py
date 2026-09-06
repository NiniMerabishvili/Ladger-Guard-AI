"""Human-in-the-loop review and automatic confidence routing."""

from uuid import UUID

from sqlalchemy.orm import Session

from app.config import settings
from app.core.exceptions import ReviewActionError, TransactionNotFoundError
from app.db.models import Decision, Transaction
from app.schemas.decision import ReviewAction
from app.services.audit_service import record_decision

_ACTION_TO_DECISION = {
    "approve": "matched",
    "reject": "flagged",
    "manual_match": "matched",
}


def apply_review_threshold(confidence: float, intended: str = "matched") -> str:
    """Low-confidence auto decisions stay pending_review — never matched/resolved."""
    if confidence < settings.REVIEW_CONFIDENCE_THRESHOLD:
        return "pending_review"
    return intended


def apply_human_review(db: Session, tx_id: UUID, action: ReviewAction) -> Decision:
    """Write a human_override audit row and update the transaction status."""
    transaction = db.get(Transaction, tx_id)
    if transaction is None:
        raise TransactionNotFoundError(f"Transaction not found: {tx_id}")

    if action.decision == "manual_match" and action.matched_transaction_id is None:
        raise ReviewActionError("manual_match requires matched_transaction_id")

    decision = _ACTION_TO_DECISION[action.decision]
    row = record_decision(
        db,
        transaction_id=tx_id,
        decision=decision,
        method="human_override",
        confidence=1.0,
        matched_transaction_id=action.matched_transaction_id,
        reasoning={"action": action.decision},
        reviewed_by=action.reviewed_by,
    )
    transaction.status = decision
    db.add(transaction)
    db.flush()
    return row
