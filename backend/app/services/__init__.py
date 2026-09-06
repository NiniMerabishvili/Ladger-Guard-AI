"""Application services: reconciliation orchestration, audit, cost tracking."""

# Keep this package init light — eager imports cause circular loads with matching/.

__all__ = [
    "apply_human_review",
    "apply_review_threshold",
    "collect_metrics",
    "get_decision_history",
    "get_estimated_cost_usd",
    "ingest_files",
    "is_open_for_matching",
    "log_call",
    "notify_n8n",
    "record_decision",
    "run_reconciliation",
    "should_notify",
]


def __getattr__(name: str):
    if name in {"get_decision_history", "record_decision"}:
        from app.services.audit_service import get_decision_history, record_decision

        return get_decision_history if name == "get_decision_history" else record_decision
    if name in {"get_estimated_cost_usd", "log_call"}:
        from app.services.cost_tracker import get_estimated_cost_usd, log_call

        return get_estimated_cost_usd if name == "get_estimated_cost_usd" else log_call
    if name == "ingest_files":
        from app.services.ingest_service import ingest_files

        return ingest_files
    if name == "collect_metrics":
        from app.services.metrics_service import collect_metrics

        return collect_metrics
    if name in {"notify_n8n", "should_notify"}:
        from app.services.n8n_service import notify_n8n, should_notify

        return notify_n8n if name == "notify_n8n" else should_notify
    if name in {"is_open_for_matching", "run_reconciliation"}:
        from app.services.reconciliation_service import is_open_for_matching, run_reconciliation

        return is_open_for_matching if name == "is_open_for_matching" else run_reconciliation
    if name in {"apply_human_review", "apply_review_threshold"}:
        from app.services.review_service import apply_human_review, apply_review_threshold

        return apply_human_review if name == "apply_human_review" else apply_review_threshold
    raise AttributeError(f"module {__name__!r} has no attribute {name!r}")
