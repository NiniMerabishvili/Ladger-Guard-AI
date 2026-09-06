"""Outbound notify: backend → n8n webhook (ClickUp workflow)."""

from typing import Any

import httpx

from app.config import settings
from app.core.logging import logger
from app.db.models import Decision

HIGH_RISK_THRESHOLD = 0.8
WEBHOOK_SECRET_HEADER = "X-Webhook-Secret"


def build_n8n_payload(decision: Decision, extra: dict[str, Any] | None = None) -> dict[str, Any]:
    reasoning = decision.reasoning or {}
    risk_score = reasoning.get("risk_score", decision.confidence)
    try:
        risk_score_f = float(risk_score)
    except (TypeError, ValueError):
        risk_score_f = float(decision.confidence)

    payload: dict[str, Any] = {
        "transaction_id": str(decision.transaction_id),
        "decision": decision.decision,
        "confidence": decision.confidence,
        "risk_score": risk_score_f,
        "risk_factors": reasoning.get("risk_factors", []),
        "reasoning": reasoning.get("explanation"),
        "method": decision.method,
        "assigned_to": "review-queue",
        "high_priority": risk_score_f > HIGH_RISK_THRESHOLD,
    }
    if extra:
        payload.update(extra)
    return payload


async def notify_n8n(decision: Decision, extra: dict[str, Any] | None = None) -> bool:
    """POST one flagged/pending_review decision to n8n. Never raises."""
    if not settings.N8N_WEBHOOK_URL:
        logger.info("N8N_WEBHOOK_URL is empty; skipping notify")
        return False

    headers: dict[str, str] = {}
    if settings.N8N_WEBHOOK_SECRET:
        headers[WEBHOOK_SECRET_HEADER] = settings.N8N_WEBHOOK_SECRET

    payload = build_n8n_payload(decision, extra)
    try:
        async with httpx.AsyncClient() as client:
            response = await client.post(
                settings.N8N_WEBHOOK_URL,
                json=payload,
                headers=headers,
                timeout=5.0,
            )
            response.raise_for_status()
        return True
    except Exception as exc:
        logger.warning("n8n notify failed: %s", exc)
        return False


def should_notify(decision: Decision) -> bool:
    return decision.decision in {"flagged", "pending_review"}
