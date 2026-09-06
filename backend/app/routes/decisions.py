"""GET /decisions/{transaction_id} — full audit trail for a transaction."""

from uuid import UUID

from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session

from app.db.models import Decision
from app.db.session import get_db
from app.schemas.decision import DecisionRead
from app.services.audit_service import get_decision_history

router = APIRouter(tags=["decisions"])


@router.get("/decisions/{transaction_id}", response_model=list[DecisionRead])
def get_decisions(transaction_id: UUID, db: Session = Depends(get_db)) -> list[Decision]:
    return get_decision_history(db, transaction_id)
