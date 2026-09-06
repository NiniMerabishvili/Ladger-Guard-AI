"""POST /ingest — upload CSVs, normalize, write to DB."""

from pathlib import Path

from fastapi import APIRouter, Depends, HTTPException, Query
from pydantic import BaseModel
from sqlalchemy.orm import Session

from app.core.exceptions import IngestionError
from app.db.session import get_db
from app.services.ingest_service import ingest_files

router = APIRouter(tags=["ingest"])


class IngestResult(BaseModel):
    bank_count: int
    ledger_count: int
    total: int


@router.post("/ingest", response_model=IngestResult)
def ingest(
    bank_path: str | None = Query(default=None),
    ledger_path: str | None = Query(default=None),
    db: Session = Depends(get_db),
) -> IngestResult:
    try:
        result = ingest_files(
            db,
            bank_path=Path(bank_path) if bank_path else None,
            ledger_path=Path(ledger_path) if ledger_path else None,
        )
        db.commit()
        return IngestResult(**result)
    except IngestionError as exc:
        db.rollback()
        raise HTTPException(status_code=400, detail=str(exc)) from exc
