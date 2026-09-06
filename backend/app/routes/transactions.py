"""GET /transactions — list with filters (status, source, date range)."""

from datetime import date
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.orm import Session

from app.db.session import get_db
from app.schemas.transaction import TransactionListItem
from app.services.transaction_service import get_transaction, list_transactions

router = APIRouter(tags=["transactions"])


@router.get("/transactions", response_model=list[TransactionListItem])
def list_transactions_route(
    status: str | None = Query(default=None),
    source: str | None = Query(default=None),
    date_from: date | None = Query(default=None),
    date_to: date | None = Query(default=None),
    project_id: UUID | None = Query(default=None),
    db: Session = Depends(get_db),
) -> list[TransactionListItem]:
    return list_transactions(
        db,
        status=status,
        source=source,
        date_from=date_from,
        date_to=date_to,
        project_id=project_id,
    )


@router.get("/transactions/{transaction_id}", response_model=TransactionListItem)
def get_transaction_route(
    transaction_id: UUID,
    db: Session = Depends(get_db),
) -> TransactionListItem:
    row = get_transaction(db, transaction_id)
    if row is None:
        raise HTTPException(status_code=404, detail="Transaction not found")
    return row
