"""List and fetch transactions for the review UI."""

from datetime import date
from uuid import UUID

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.db.models import Decision, Transaction
from app.schemas.decision import DecisionRead
from app.schemas.transaction import TransactionListItem


def latest_decisions_by_tx(db: Session, tx_ids: list[UUID]) -> dict[UUID, DecisionRead]:
    if not tx_ids:
        return {}
    rows = db.scalars(
        select(Decision)
        .where(Decision.transaction_id.in_(tx_ids))
        .order_by(Decision.created_at.desc(), Decision.id.desc())
    ).all()
    latest: dict[UUID, DecisionRead] = {}
    for row in rows:
        if row.transaction_id not in latest:
            latest[row.transaction_id] = DecisionRead.model_validate(row)
    return latest


def _to_list_item(row: Transaction, latest: dict[UUID, DecisionRead]) -> TransactionListItem:
    return TransactionListItem.model_validate(row).model_copy(
        update={"latest_decision": latest.get(row.id)}
    )


def list_transactions(
    db: Session,
    *,
    status: str | None = None,
    source: str | None = None,
    date_from: date | None = None,
    date_to: date | None = None,
) -> list[TransactionListItem]:
    stmt = select(Transaction)
    if status:
        stmt = stmt.where(Transaction.status == status)
    if source:
        stmt = stmt.where(Transaction.source == source)
    if date_from:
        stmt = stmt.where(Transaction.date >= date_from)
    if date_to:
        stmt = stmt.where(Transaction.date <= date_to)
    stmt = stmt.order_by(Transaction.date.desc(), Transaction.created_at.desc())
    rows = list(db.scalars(stmt).all())
    latest = latest_decisions_by_tx(db, [row.id for row in rows])
    return [_to_list_item(row, latest) for row in rows]


def get_transaction(db: Session, tx_id: UUID) -> TransactionListItem | None:
    row = db.get(Transaction, tx_id)
    if row is None:
        return None
    latest = latest_decisions_by_tx(db, [row.id])
    return _to_list_item(row, latest)
