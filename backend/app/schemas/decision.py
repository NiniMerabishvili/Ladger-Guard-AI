"""Pydantic schemas for decisions and human review actions."""

from datetime import datetime
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field


class DecisionRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: UUID
    transaction_id: UUID
    matched_transaction_id: UUID | None = None
    decision: str
    method: str
    confidence: float
    reasoning: dict | None = None
    model_used: str | None = None
    reviewed_by: str | None = None
    matching_run_id: UUID | None = None
    created_at: datetime


class ReviewAction(BaseModel):
    decision: str = Field(..., pattern="^(approve|reject|manual_match)$")
    reviewed_by: str = "reviewer"
    matched_transaction_id: UUID | None = None
