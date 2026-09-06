"""Pydantic schemas for transactions."""

from datetime import date
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field

from app.schemas.decision import DecisionRead


class TransactionCreate(BaseModel):
    source: str = Field(..., pattern="^(bank|ledger)$")
    date: date
    amount: float
    currency: str = Field(..., min_length=3, max_length=3)
    description: str
    counterparty: str | None = None


class TransactionRead(TransactionCreate):
    model_config = ConfigDict(from_attributes=True)

    id: UUID
    status: str


class TransactionListItem(TransactionRead):
    latest_decision: DecisionRead | None = None
