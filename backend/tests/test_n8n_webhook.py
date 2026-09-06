"""n8n notify payload and webhook secret checks."""

from unittest.mock import AsyncMock, MagicMock, patch
from uuid import uuid4

import pytest
from fastapi.testclient import TestClient

from app.config import settings
from app.db.models import Decision
from app.db.session import get_db
from app.main import app
from app.services.n8n_service import build_n8n_payload, should_notify


def _decision(**kwargs: object) -> Decision:
    defaults = {
        "transaction_id": uuid4(),
        "decision": "pending_review",
        "method": "llm_agent",
        "confidence": 0.65,
        "reasoning": {
            "risk_score": 0.65,
            "risk_factors": ["unknown_counterparty"],
            "explanation": "New vendor wire",
        },
    }
    defaults.update(kwargs)
    return Decision(**defaults)


def test_payload_matches_plan_fields() -> None:
    row = _decision()
    payload = build_n8n_payload(row)
    assert payload["transaction_id"] == str(row.transaction_id)
    assert payload["decision"] == "pending_review"
    assert payload["confidence"] == 0.65
    assert payload["risk_factors"] == ["unknown_counterparty"]
    assert payload["reasoning"] == "New vendor wire"
    assert payload["method"] == "llm_agent"
    assert payload["high_priority"] is False


def test_high_priority_when_risk_score_above_0_8() -> None:
    row = _decision(
        confidence=0.91,
        reasoning={"risk_score": 0.91, "risk_factors": ["unusual_amount"], "explanation": "large"},
    )
    assert build_n8n_payload(row)["high_priority"] is True


def test_only_flagged_and_pending_review_are_notified() -> None:
    assert should_notify(_decision(decision="flagged")) is True
    assert should_notify(_decision(decision="pending_review")) is True
    assert should_notify(_decision(decision="matched")) is False


@pytest.mark.parametrize("secret_ok", [True])
def test_webhook_endpoint_forwards_when_secret_matches(secret_ok: bool) -> None:
    db = MagicMock()

    def _override() -> MagicMock:
        yield db

    app.dependency_overrides[get_db] = _override
    previous = settings.N8N_WEBHOOK_SECRET
    settings.N8N_WEBHOOK_SECRET = "test-secret"
    try:
        client = TestClient(app)
        with patch(
            "app.routes.webhook.notify_n8n",
            new=AsyncMock(return_value=True),
        ) as mocked:
            response = client.post(
                "/webhook/decision",
                json={
                    "transaction_id": str(uuid4()),
                    "decision": "flagged",
                    "confidence": 0.9,
                    "risk_factors": ["unusual_amount"],
                    "reasoning": "large wire",
                    "method": "llm_agent",
                    "amount": 5000,
                },
                headers={"X-Webhook-Secret": "test-secret"},
            )
        assert response.status_code == 200
        assert response.json()["status"] == "sent"
        mocked.assert_awaited()
    finally:
        settings.N8N_WEBHOOK_SECRET = previous
        app.dependency_overrides.clear()


def test_webhook_rejects_bad_secret() -> None:
    previous = settings.N8N_WEBHOOK_SECRET
    settings.N8N_WEBHOOK_SECRET = "test-secret"
    try:
        client = TestClient(app)
        response = client.post(
            "/webhook/decision",
            json={
                "transaction_id": str(uuid4()),
                "decision": "flagged",
                "confidence": 0.9,
                "method": "llm_agent",
            },
            headers={"X-Webhook-Secret": "wrong"},
        )
        assert response.status_code == 401
    finally:
        settings.N8N_WEBHOOK_SECRET = previous
