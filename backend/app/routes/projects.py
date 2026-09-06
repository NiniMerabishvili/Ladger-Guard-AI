"""Project API — create, list, open saved reconciliation workspaces."""

from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, Field
from sqlalchemy.orm import Session

from app.db.session import get_db
from app.services.project_service import (
    create_project,
    get_project,
    list_projects,
    project_to_dict,
)

router = APIRouter(tags=["projects"])


class ProjectCreate(BaseModel):
    name: str | None = Field(default=None, max_length=200)


class ProjectRead(BaseModel):
    id: str
    name: str
    status: str
    bank_filename: str | None = None
    ledger_filename: str | None = None
    summary: dict | None = None
    total_transactions: int = 0
    matched: int = 0
    pending_review: int = 0
    flagged: int = 0
    created_at: str | None = None
    updated_at: str | None = None


@router.get("/projects", response_model=list[ProjectRead])
def list_projects_route(db: Session = Depends(get_db)) -> list[ProjectRead]:
    return [ProjectRead(**project_to_dict(row)) for row in list_projects(db)]


@router.post("/projects", response_model=ProjectRead)
def create_project_route(
    body: ProjectCreate | None = None,
    db: Session = Depends(get_db),
) -> ProjectRead:
    name = body.name if body else None
    project = create_project(db, name=name)
    db.commit()
    db.refresh(project)
    return ProjectRead(**project_to_dict(project))


@router.get("/projects/{project_id}", response_model=ProjectRead)
def get_project_route(project_id: UUID, db: Session = Depends(get_db)) -> ProjectRead:
    project = get_project(db, project_id)
    if project is None:
        raise HTTPException(status_code=404, detail="Project not found")
    return ProjectRead(**project_to_dict(project))
