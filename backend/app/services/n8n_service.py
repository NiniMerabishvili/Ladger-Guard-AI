"""Outbound notify: backend → n8n webhook (ClickUp workflow)."""

from typing import Any

import httpx

from app.config import settings
from app.core.logging import logger
from app.db.models import Decision, Transaction

HIGH_RISK_THRESHOLD = 0.8
WEBHOOK_SECRET_HEADER = "X-Webhook-Secret"


def _tx_fields(transaction: Transaction | None) -> dict[str, Any]:
    if transaction is None:
        return {}
    return {
        "description": transaction.description,
        "counterparty": transaction.counterparty,
        "amount": float(transaction.amount),
        "currency": transaction.currency,
        "date": transaction.date.isoformat(),
        "source": transaction.source,
        # Same label reviewers see in the Review queue (not the UUID).
        "task_name": transaction.description,
    }


def build_n8n_payload(
    decision: Decision,
    extra: dict[str, Any] | None = None,
    *,
    transaction: Transaction | None = None,
) -> dict[str, Any]:
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
    payload.update(_tx_fields(transaction))
    if extra:
        payload.update(extra)

    # Prefer review-queue style name; fall back only when description is missing.
    name = payload.get("task_name") or payload.get("description")
    if isinstance(name, str) and name.strip():
        payload["task_name"] = name.strip()
    else:
        payload["task_name"] = f"{decision.decision} — {decision.transaction_id}"
    return payload


async def notify_n8n(
    decision: Decision,
    extra: dict[str, Any] | None = None,
    *,
    transaction: Transaction | None = None,
) -> bool:
    """POST one flagged/pending_review decision to n8n. Never raises."""
    payload = build_n8n_payload(decision, extra, transaction=transaction)
    return post_n8n_payload(payload)


def post_n8n_payload(payload: dict[str, Any]) -> bool:
    """Sync POST used by BackgroundTasks after reconcile commits."""
    if not settings.N8N_WEBHOOK_URL:
        logger.info("N8N_WEBHOOK_URL is empty; skipping notify")
        return False

    headers: dict[str, str] = {}
    if settings.N8N_WEBHOOK_SECRET:
        headers[WEBHOOK_SECRET_HEADER] = settings.N8N_WEBHOOK_SECRET

    try:
        response = httpx.post(
            settings.N8N_WEBHOOK_URL,
            json=payload,
            headers=headers,
            timeout=3.0,
        )
        response.raise_for_status()
        return True
    except Exception as exc:
        logger.warning("n8n notify failed: %s", exc)
        return False


def should_notify(decision: Decision) -> bool:
    return decision.decision in {"flagged", "pending_review"}
