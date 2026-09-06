"""POST /webhook/decision — notify n8n on flagged / pending_review."""

from fastapi import APIRouter, Header, HTTPException
from pydantic import BaseModel

from app.config import settings
from app.db.models import Decision
from app.services.n8n_service import WEBHOOK_SECRET_HEADER, notify_n8n, should_notify

router = APIRouter(tags=["webhook"])


class WebhookDecisionBody(BaseModel):
    transaction_id: str
    decision: str
    confidence: float
    risk_factors: list[str] = []
    reasoning: str | None = None
    method: str
    amount: float | None = None


def _check_secret(x_webhook_secret: str | None) -> None:
    expected = settings.N8N_WEBHOOK_SECRET
    if not expected:
        return
    if x_webhook_secret != expected:
        raise HTTPException(status_code=401, detail="Invalid webhook secret")


@router.post("/webhook/decision")
async def webhook_decision(
    body: WebhookDecisionBody,
    x_webhook_secret: str | None = Header(default=None, alias=WEBHOOK_SECRET_HEADER),
) -> dict[str, str]:
    _check_secret(x_webhook_secret)
    decision = Decision(
        transaction_id=body.transaction_id,
        decision=body.decision,
        method=body.method,
        confidence=body.confidence,
        reasoning={
            "risk_factors": body.risk_factors,
            "explanation": body.reasoning,
            "risk_score": body.confidence,
        },
    )
    if not should_notify(decision):
        return {"status": "ignored", "reason": "not flagged or pending_review"}

    extra = {"amount": body.amount} if body.amount is not None else None
    sent = await notify_n8n(decision, extra=extra)
    return {"status": "sent" if sent else "skipped"}
