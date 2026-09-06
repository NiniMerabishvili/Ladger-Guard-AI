"""POST /reconcile/run — run Tier1 → Tier2 → Agent pipeline."""

from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, Query
from pydantic import BaseModel
from sqlalchemy.orm import Session

from app.db.session import get_db
from app.services.reconciliation_service import run_reconciliation

router = APIRouter(tags=["reconcile"])


class ReconcileResult(BaseModel):
    matching_run_id: str
    processed: int
    skipped_resolved: int
    exact_rule: int
    semantic_match: int
    llm_agent: int
    decisions_written: int


@router.post("/reconcile/run", response_model=ReconcileResult)
def reconcile_run(
    run_id: UUID | None = Query(default=None),
    db: Session = Depends(get_db),
) -> ReconcileResult:
    try:
        summary = run_reconciliation(db, run_id=run_id)
        db.commit()
        return ReconcileResult(**summary)
    except Exception as exc:
        db.rollback()
        raise HTTPException(status_code=500, detail=str(exc)) from exc
