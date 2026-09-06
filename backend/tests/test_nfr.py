"""Section 7 NFRs: explainability, cost awareness, idempotency."""

import asyncio
from dataclasses import dataclass
from datetime import date
from decimal import Decimal
from unittest.mock import MagicMock
from uuid import UUID, uuid4

from app.agent.anomaly_agent import FALLBACK_RISK_SCORE, RunContext, fallback_anomaly, score_anomaly
from app.agent.prompts import ANOMALY_SYSTEM_PROMPT, build_anomaly_prompt
from app.db.models import Decision, Transaction
from app.services.cost_tracker import get_call_log, get_estimated_cost_usd, reset
from app.services.metrics_service import compute_metrics
from app.services.reconciliation_service import run_reconciliation

EXPLAINABILITY_RULE = (
    "If you cannot justify with specific evidence, set risk_score low and explain why, "
    "rather than guessing."
)


@dataclass
class FakeTx:
    amount: float = 5000.0
    date: date = date(2026, 9, 1)
    description: str = "UNKNOWN VENDOR WIRE"
    counterparty: str = "ACME LLC"
    currency: str = "USD"
    source: str = "bank"


class MockProvider:
    def __init__(self, payload: object | None = None, error: Exception | None = None) -> None:
        self.payload = payload
        self.error = error

    async def generate_structured(self, prompt: str, schema: dict) -> dict:
        if self.error:
            raise self.error
        assert isinstance(self.payload, dict)
        return self.payload


def _tx(*, source: str, amount: str, status: str = "unmatched") -> Transaction:
    return Transaction(
        id=uuid4(),
        source=source,
        date=date(2026, 9, 1),
        amount=Decimal(amount),
        currency="USD",
        description="ACME",
        counterparty="ACME",
        status=status,
    )


# --- 7.1 Explainability > Accuracy ---


def test_prompt_requires_evidence_over_guessing() -> None:
    assert EXPLAINABILITY_RULE in ANOMALY_SYSTEM_PROMPT
    prompt = build_anomaly_prompt(FakeTx(), prior_context=None)
    assert EXPLAINABILITY_RULE in prompt


def test_schema_failure_never_becomes_high_risk_flag() -> None:
    """Invalid structured output → low-confidence fallback, never a high-risk flag."""
    reset()
    provider = MockProvider(
        payload={
            "risk_score": 0.99,
            "risk_factors": ["made_up_factor"],
            "explanation": "guessing wildly",
        }
    )
    result = asyncio.run(score_anomaly(FakeTx(), RunContext(), provider=provider))
    assert result == fallback_anomaly()
    assert result["risk_score"] == FALLBACK_RISK_SCORE
    assert result["risk_score"] < 0.7
    assert result["risk_factors"] == []
    # Failed validation must not bill a successful LLM call.
    assert get_call_log() == []


# --- 7.2 Cost Awareness ---


def test_successful_llm_call_is_cost_tracked() -> None:
    reset()
    provider = MockProvider(
        payload={
            "risk_score": 0.4,
            "risk_factors": [],
            "explanation": "Small coffee purchase looks normal.",
        }
    )
    provider.model = "claude-sonnet-4-6"  # type: ignore[attr-defined]
    asyncio.run(score_anomaly(FakeTx(), RunContext(), provider=provider))
    assert get_estimated_cost_usd() > 0
    assert get_call_log()[0].model == "claude-sonnet-4-6"


def test_embedding_provider_logs_through_cost_tracker() -> None:
    reset()

    class TrackingEmbedder:
        model_name = "fake-embed"

        def embed(self, text: str) -> list[float]:
            from app.services.cost_tracker import log_call

            log_call("local", self.model_name, 1)
            return [0.1] * 384

    vector = TrackingEmbedder().embed("STARBUCKS")
    assert len(vector) == 384
    assert get_call_log()[0].provider == "local"
    assert get_estimated_cost_usd() == 0.0  # local embeddings are free in the mock table


def test_dashboard_metrics_include_running_cost_total() -> None:
    metrics = compute_metrics(
        {"matched": 7, "pending_review": 2, "flagged": 1},
        {"exact_rule": 5, "llm_agent": 2},
        cost_usd=0.006,
    )
    assert metrics.estimated_llm_cost_usd == 0.006


# --- 7.3 Idempotency ---


async def _agent(_tx: Transaction, _ctx: object) -> dict:
    return {"risk_score": 0.2, "risk_factors": [], "explanation": "routine"}


def test_decisions_carry_matching_run_id_and_second_run_is_noop() -> None:
    bank = _tx(source="bank", amount="50.00")
    ledger = _tx(source="ledger", amount="50.00")
    db = MagicMock()
    added: list[object] = []
    db.add.side_effect = added.append
    db.get.side_effect = lambda _model, pk: ledger if pk == ledger.id else None
    run_id = uuid4()

    first = run_reconciliation(
        db,
        run_id=run_id,
        bank_rows=[bank],
        ledger_rows=[ledger],
        skip_semantic=True,
        notify=False,
        score_fn=_agent,
    )
    decision_rows = [row for row in added if isinstance(row, Decision)]
    assert first["decisions_written"] == 1
    assert len(decision_rows) == 1
    assert decision_rows[0].matching_run_id == run_id
    assert isinstance(decision_rows[0].matching_run_id, UUID)

    before = len(added)
    second = run_reconciliation(
        db,
        run_id=uuid4(),
        bank_rows=[bank],
        ledger_rows=[ledger],
        skip_semantic=True,
        notify=False,
        score_fn=_agent,
    )
    assert second["decisions_written"] == 0
    assert second["processed"] == 0
    assert len(added) == before
