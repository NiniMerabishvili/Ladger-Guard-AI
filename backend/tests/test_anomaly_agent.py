"""Tests for the anomaly scoring agent (mocked LLM)."""

import asyncio
from dataclasses import dataclass
from datetime import date

import pytest
from pydantic import ValidationError

from app.agent.anomaly_agent import (
    RunContext,
    fallback_anomaly,
    score_anomaly,
    validate_anomaly_output,
)
from app.agent.prompts import ANOMALY_SCHEMA, build_anomaly_prompt


@dataclass
class FakeTx:
    amount: float = 5000.0
    date: date = date(2026, 9, 1)
    description: str = "UNKNOWN VENDOR WIRE"
    counterparty: str = "ACME LLC"
    currency: str = "USD"
    source: str = "bank"


class MockProvider:
    def __init__(self, responses: list[object] | None = None, error: Exception | None = None) -> None:
        self.responses = list(responses or [])
        self.error = error
        self.prompts: list[str] = []
        self.schemas: list[dict] = []

    async def generate_structured(self, prompt: str, schema: dict) -> dict:
        self.prompts.append(prompt)
        self.schemas.append(schema)
        if self.error:
            raise self.error
        payload = self.responses.pop(0)
        if isinstance(payload, Exception):
            raise payload
        return payload  # type: ignore[return-value]


VALID_OUTPUT = {
    "risk_score": 0.81,
    "risk_factors": ["unknown_counterparty", "unusual_amount"],
    "explanation": "Wire to a new vendor for an unusually large amount.",
}


def test_schema_validation_success() -> None:
    assert validate_anomaly_output(VALID_OUTPUT)["risk_score"] == 0.81


def test_schema_validation_failure() -> None:
    with pytest.raises(ValidationError):
        validate_anomaly_output({"risk_score": 1.5, "risk_factors": [], "explanation": "bad"})
    with pytest.raises(ValueError):
        validate_anomaly_output(
            {
                "risk_score": 0.4,
                "risk_factors": ["not_a_real_factor"],
                "explanation": "bad factor",
            }
        )


def test_invalid_llm_output_uses_low_confidence_fallback() -> None:
    provider = MockProvider(
        responses=[{"risk_score": 0.99, "risk_factors": ["made_up"], "explanation": "guess"}]
    )
    result = asyncio.run(score_anomaly(FakeTx(), RunContext(), provider=provider))
    assert result == fallback_anomaly()
    assert result["risk_score"] == 0.1
    assert result["explanation"] == "Agent output could not be validated"


def test_llm_exception_uses_fallback_instead_of_crashing() -> None:
    provider = MockProvider(error=RuntimeError("api down"))
    result = asyncio.run(score_anomaly(FakeTx(), RunContext(), provider=provider))
    assert result["explanation"] == "Agent output could not be validated"


def test_session_memory_applied_on_second_call() -> None:
    context = RunContext()
    provider = MockProvider(responses=[VALID_OUTPUT, VALID_OUTPUT])
    tx = FakeTx()

    first = asyncio.run(score_anomaly(tx, context, provider=provider))
    assert first["risk_score"] == 0.81
    assert context.get_prior_context("ACME LLC") is not None

    asyncio.run(score_anomaly(tx, context, provider=provider))
    assert "already flagged" in provider.prompts[1]
    assert "ACME LLC" in build_anomaly_prompt(tx, context.get_prior_context("ACME LLC"))
    assert provider.schemas[0] == ANOMALY_SCHEMA
