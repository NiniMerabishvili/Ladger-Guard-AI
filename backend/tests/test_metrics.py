"""Dashboard metrics and mock cost tracker."""

from unittest.mock import MagicMock

from fastapi.testclient import TestClient

from app.db.session import get_db
from app.main import app
from app.services.cost_tracker import get_estimated_cost_usd, log_call, reset
from app.services.metrics_service import LABOR_SAVINGS_NOTE, compute_metrics


def test_cost_tracker_accumulates_mock_spend() -> None:
    reset()
    log_call("local", "all-MiniLM-L6-v2", 2)
    log_call("claude", "claude-sonnet-4-6", 1)
    assert get_estimated_cost_usd() == 0.003
    reset()


def test_compute_metrics_percentages_and_labor_assumption() -> None:
    reset()
    metrics = compute_metrics(
        {"matched": 7, "pending_review": 2, "flagged": 1},
        {"exact_rule": 6, "semantic_match": 1, "llm_agent": 2},
        cost_usd=0.012,
    )
    assert metrics.total_transactions == 10
    assert metrics.auto_matched_pct == 70.0
    assert metrics.pending_review_pct == 20.0
    assert metrics.flagged_pct == 10.0
    assert metrics.method_breakdown.exact_rule == 6
    assert metrics.estimated_llm_cost_usd == 0.012
    assert metrics.estimated_manual_labor_savings_usd == 17.5
    assert "Assumption-based" in metrics.labor_savings_note
    assert metrics.false_positive_rate is None
    assert LABOR_SAVINGS_NOTE.startswith("Assumption-based")


def test_get_metrics_endpoint() -> None:
    reset()
    log_call("gemini", "gemini-2.0-flash", 1)
    db = MagicMock()
    status_result = MagicMock()
    status_result.all.return_value = [("matched", 8), ("pending_review", 2)]
    method_result = MagicMock()
    method_result.all.return_value = [("exact_rule", 7), ("llm_agent", 3)]
    db.execute.side_effect = [status_result, method_result]

    def _override() -> MagicMock:
        yield db

    app.dependency_overrides[get_db] = _override
    try:
        client = TestClient(app)
        response = client.get("/metrics")
    finally:
        app.dependency_overrides.clear()
        reset()

    assert response.status_code == 200
    payload = response.json()
    assert payload["total_transactions"] == 10
    assert payload["auto_matched_pct"] == 80.0
    assert payload["method_breakdown"]["exact_rule"] == 7
    assert payload["estimated_llm_cost_usd"] == 0.0002
    assert "Assumption-based" in payload["labor_savings_note"]
