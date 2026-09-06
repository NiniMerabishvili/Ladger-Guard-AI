"""Dashboard aggregates for GET /metrics."""

from collections import Counter

from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.db.models import Decision, Transaction
from app.schemas.metrics import MethodBreakdown, MetricsRead
from app.services.cost_tracker import (
    MANUAL_LABOR_USD_PER_AUTO_MATCH,
    get_estimated_cost_usd,
)

LABOR_SAVINGS_NOTE = (
    f"Assumption-based: ${MANUAL_LABOR_USD_PER_AUTO_MATCH:.2f} per auto-matched "
    "transaction. Not a measured production figure."
)


def _pct(part: int, whole: int) -> float:
    if whole <= 0:
        return 0.0
    return round(100.0 * part / whole, 2)


def compute_metrics(
    status_counts: dict[str, int],
    method_counts: dict[str, int],
    *,
    cost_usd: float,
    false_positive_rate: float | None = None,
) -> MetricsRead:
    total = sum(status_counts.values())
    matched = status_counts.get("matched", 0)
    pending = status_counts.get("pending_review", 0)
    flagged = status_counts.get("flagged", 0)
    return MetricsRead(
        total_transactions=total,
        auto_matched_pct=_pct(matched, total),
        pending_review_pct=_pct(pending, total),
        flagged_pct=_pct(flagged, total),
        method_breakdown=MethodBreakdown(
            exact_rule=method_counts.get("exact_rule", 0),
            semantic_match=method_counts.get("semantic_match", 0),
            llm_agent=method_counts.get("llm_agent", 0),
            human_override=method_counts.get("human_override", 0),
        ),
        estimated_llm_cost_usd=cost_usd,
        estimated_manual_labor_savings_usd=round(matched * MANUAL_LABOR_USD_PER_AUTO_MATCH, 2),
        labor_savings_note=LABOR_SAVINGS_NOTE,
        false_positive_rate=false_positive_rate,
    )


def collect_metrics(db: Session) -> MetricsRead:
    status_rows = db.execute(
        select(Transaction.status, func.count()).group_by(Transaction.status)
    ).all()
    method_rows = db.execute(
        select(Decision.method, func.count()).group_by(Decision.method)
    ).all()
    return compute_metrics(
        Counter({status: count for status, count in status_rows}),
        Counter({method: count for method, count in method_rows}),
        cost_usd=get_estimated_cost_usd(),
        false_positive_rate=None,
    )
