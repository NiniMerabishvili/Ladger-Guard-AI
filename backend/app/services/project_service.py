"""Project CRUD and summary snapshots."""

from __future__ import annotations

from datetime import datetime, timezone
from typing import Any
from uuid import UUID, uuid4

from sqlalchemy import delete, func, select
from sqlalchemy.orm import Session

from app.db.models import Decision, Project, Transaction
from app.services.metrics_service import collect_metrics


def create_project(db: Session, *, name: str | None = None) -> Project:
    stamp = datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M")
    project = Project(
        id=uuid4(),
        name=(name or "").strip() or f"Project {stamp}",
        status="open",
    )
    db.add(project)
    db.flush()
    return project


def list_projects(db: Session) -> list[Project]:
    return list(db.scalars(select(Project).order_by(Project.created_at.desc())).all())


def get_project(db: Session, project_id: UUID) -> Project | None:
    return db.get(Project, project_id)


def clear_project_data(db: Session, project_id: UUID) -> None:
    """Delete decisions + transactions for one project (keep the project row)."""
    tx_ids = list(
        db.scalars(select(Transaction.id).where(Transaction.project_id == project_id)).all()
    )
    if tx_ids:
        db.execute(delete(Decision).where(Decision.transaction_id.in_(tx_ids)))
        db.execute(
            delete(Decision).where(Decision.matched_transaction_id.in_(tx_ids))
        )
        db.execute(delete(Transaction).where(Transaction.project_id == project_id))
    db.flush()


def project_counts(db: Session, project_id: UUID) -> dict[str, int]:
    rows = db.execute(
        select(Transaction.status, func.count())
        .where(Transaction.project_id == project_id)
        .group_by(Transaction.status)
    ).all()
    counts = {status: int(count) for status, count in rows}
    total = sum(counts.values())
    return {
        "total": total,
        "matched": counts.get("matched", 0),
        "pending_review": counts.get("pending_review", 0),
        "flagged": counts.get("flagged", 0),
        "unmatched": counts.get("unmatched", 0),
    }


def refresh_project_summary(
    db: Session,
    project: Project,
    *,
    ingest: dict[str, Any] | None = None,
    reconcile: dict[str, Any] | None = None,
) -> Project:
    metrics = collect_metrics(db, project_id=project.id)
    counts = project_counts(db, project.id)
    summary: dict[str, Any] = {
        "counts": counts,
        "metrics": metrics.model_dump(),
    }
    if ingest:
        summary["ingest"] = ingest
    elif project.summary and isinstance(project.summary, dict) and "ingest" in project.summary:
        summary["ingest"] = project.summary["ingest"]
    if reconcile:
        summary["reconcile"] = {
            key: value
            for key, value in reconcile.items()
            if key != "notify_payloads"
        }
    elif project.summary and isinstance(project.summary, dict) and "reconcile" in project.summary:
        summary["reconcile"] = project.summary["reconcile"]

    project.summary = summary
    if counts["total"] > 0 and reconcile:
        project.status = "completed"
    project.updated_at = datetime.now(timezone.utc).replace(tzinfo=None)
    db.add(project)
    db.flush()
    return project


def project_to_dict(project: Project) -> dict[str, Any]:
    summary = project.summary if isinstance(project.summary, dict) else {}
    counts = summary.get("counts") or {}
    return {
        "id": str(project.id),
        "name": project.name,
        "status": project.status,
        "bank_filename": project.bank_filename,
        "ledger_filename": project.ledger_filename,
        "summary": summary,
        "total_transactions": int(counts.get("total") or 0),
        "matched": int(counts.get("matched") or 0),
        "pending_review": int(counts.get("pending_review") or 0),
        "flagged": int(counts.get("flagged") or 0),
        "created_at": project.created_at.isoformat() if project.created_at else None,
        "updated_at": project.updated_at.isoformat() if project.updated_at else None,
    }
