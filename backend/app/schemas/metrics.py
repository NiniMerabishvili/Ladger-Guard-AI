"""Pydantic schemas for dashboard metrics."""

from pydantic import BaseModel


class MethodBreakdown(BaseModel):
    exact_rule: int = 0
    semantic_match: int = 0
    llm_agent: int = 0
    human_override: int = 0


class MetricsRead(BaseModel):
    total_transactions: int
    auto_matched_pct: float
    pending_review_pct: float
    flagged_pct: float
    method_breakdown: MethodBreakdown
    estimated_llm_cost_usd: float
    estimated_manual_labor_savings_usd: float
    labor_savings_note: str
    false_positive_rate: float | None = None
