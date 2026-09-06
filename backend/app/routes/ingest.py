"""POST /ingest — upload CSVs into a project workspace."""

from pathlib import Path
from uuid import UUID

from fastapi import APIRouter, Depends, File, Form, HTTPException, Query, UploadFile
from pydantic import BaseModel
from sqlalchemy.orm import Session

from app.core.exceptions import IngestionError
from app.db.session import get_db
from app.services.ingest_service import ingest_files, ingest_uploads
from app.services.project_service import create_project, refresh_project_summary

router = APIRouter(tags=["ingest"])

MAX_UPLOAD_BYTES = 5 * 1024 * 1024  # 5 MB per file


class IngestResult(BaseModel):
    bank_count: int
    ledger_count: int
    total: int
    project_id: str | None = None


async def _read_upload(upload: UploadFile, label: str) -> bytes:
    raw = await upload.read()
    if len(raw) > MAX_UPLOAD_BYTES:
        raise IngestionError(f"{label} exceeds {MAX_UPLOAD_BYTES // (1024 * 1024)} MB limit")
    return raw


@router.post("/ingest", response_model=IngestResult)
async def ingest(
    bank_file: UploadFile | None = File(default=None),
    ledger_file: UploadFile | None = File(default=None),
    project_id: UUID | None = Form(default=None),
    bank_path: str | None = Query(default=None),
    ledger_path: str | None = Query(default=None),
    project_id_query: UUID | None = Query(default=None, alias="project_id"),
    db: Session = Depends(get_db),
) -> IngestResult:
    """Prefer multipart uploads from the UI; path query params remain for scripts/Docker."""
    active_project_id = project_id or project_id_query
    try:
        if bank_file is not None or ledger_file is not None:
            if bank_file is None or ledger_file is None:
                raise IngestionError("Upload both bank_file and ledger_file")
            if active_project_id is None:
                active_project_id = create_project(db).id
            result = ingest_uploads(
                db,
                bank_bytes=await _read_upload(bank_file, "bank_file"),
                ledger_bytes=await _read_upload(ledger_file, "ledger_file"),
                bank_name=bank_file.filename or "bank_statement.csv",
                ledger_name=ledger_file.filename or "internal_ledger.csv",
                project_id=active_project_id,
            )
            from app.services.project_service import get_project

            project = get_project(db, active_project_id)
            if project is not None:
                refresh_project_summary(
                    db,
                    project,
                    ingest={
                        "bank_count": result["bank_count"],
                        "ledger_count": result["ledger_count"],
                        "total": result["total"],
                    },
                )
        else:
            result = ingest_files(
                db,
                bank_path=Path(bank_path) if bank_path else None,
                ledger_path=Path(ledger_path) if ledger_path else None,
                project_id=active_project_id,
            )
        db.commit()
        return IngestResult(
            bank_count=int(result["bank_count"]),
            ledger_count=int(result["ledger_count"]),
            total=int(result["total"]),
            project_id=str(active_project_id) if active_project_id else None,
        )
    except IngestionError as exc:
        db.rollback()
        raise HTTPException(status_code=400, detail=str(exc)) from exc
