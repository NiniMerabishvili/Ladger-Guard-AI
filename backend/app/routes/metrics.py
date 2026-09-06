"""GET /metrics — dashboard aggregates."""

from uuid import UUID

from fastapi import APIRouter, Depends, Query
from sqlalchemy.orm import Session

from app.db.session import get_db
from app.schemas.metrics import MetricsRead
from app.services.metrics_service import collect_metrics

router = APIRouter(tags=["metrics"])


@router.get("/metrics", response_model=MetricsRead)
def get_metrics(
    project_id: UUID | None = Query(default=None),
    db: Session = Depends(get_db),
) -> MetricsRead:
    return collect_metrics(db, project_id=project_id)
