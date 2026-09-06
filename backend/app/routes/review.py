"""POST /review/{tx_id} — human approve / reject / manual-match."""

from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session

from app.core.exceptions import ReviewActionError, TransactionNotFoundError
from app.db.session import get_db
from app.schemas.decision import DecisionRead, ReviewAction
from app.services.review_service import apply_human_review

router = APIRouter(tags=["review"])


@router.post("/review/{tx_id}", response_model=DecisionRead)
def review_transaction(
    tx_id: UUID,
    action: ReviewAction,
    db: Session = Depends(get_db),
) -> DecisionRead:
    try:
        row = apply_human_review(db, tx_id, action)
        db.commit()
        db.refresh(row)
        return row
    except TransactionNotFoundError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc
    except ReviewActionError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
