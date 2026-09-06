"""POST /reconcile/run — run Tier1 → Tier2 → Agent pipeline."""

from typing import Any
from uuid import UUID

from fastapi import APIRouter, BackgroundTasks, Depends, HTTPException, Query
from pydantic import BaseModel
from sqlalchemy.orm import Session

from app.db.session import get_db
from app.services.n8n_service import post_n8n_payload
from app.services.project_service import get_project, refresh_project_summary
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
    project_id: str | None = None


@router.post("/reconcile/run", response_model=ReconcileResult)
def reconcile_run(
    background_tasks: BackgroundTasks,
    run_id: UUID | None = Query(default=None),
    project_id: UUID | None = Query(default=None),
    db: Session = Depends(get_db),
) -> ReconcileResult:
    try:
        if project_id is not None and get_project(db, project_id) is None:
            raise HTTPException(status_code=404, detail="Project not found")
        summary = run_reconciliation(db, run_id=run_id, project_id=project_id)
        payloads: list[dict[str, Any]] = list(summary.pop("notify_payloads", []))
        if project_id is not None:
            project = get_project(db, project_id)
            if project is not None:
                refresh_project_summary(db, project, reconcile=summary)
        db.commit()
        for payload in payloads:
            background_tasks.add_task(post_n8n_payload, payload)
        return ReconcileResult(**summary, project_id=str(project_id) if project_id else None)
    except HTTPException:
        raise
    except Exception as exc:
        db.rollback()
        raise HTTPException(status_code=500, detail=str(exc)) from exc
