"""ModelProvider abstraction: factory, retry, same-case Claude vs Gemini."""

import asyncio
from dataclasses import dataclass
from datetime import date

import pytest

from app.agent.compare import compare_providers
from app.agent.model_provider import (
    ClaudeProvider,
    GeminiProvider,
    get_model_provider,
    is_auth_error,
    retry_generate,
)
from app.config import settings


@dataclass
class FakeTx:
    amount: float
    date: date
    description: str
    counterparty: str
    currency: str = "USD"
    source: str = "bank"


CASES = [
    FakeTx(5000, date(2026, 9, 1), "UNKNOWN VENDOR WIRE", "ACME LLC"),
    FakeTx(4.50, date(2026, 9, 2), "STARBUCKS STORE 11847", "STARBUCKS"),
]


class RecordingProvider:
    def __init__(self, name: str, output: dict) -> None:
        self.name = name
        self.model = name
        self.output = output
        self.calls = 0

    async def generate_structured(self, prompt: str, schema: dict) -> dict:
        self.calls += 1
        return dict(self.output)


def test_factory_returns_claude_or_gemini() -> None:
    previous = settings.LLM_PROVIDER
    try:
        settings.LLM_PROVIDER = "gemini"
        assert isinstance(get_model_provider(), GeminiProvider)
        settings.LLM_PROVIDER = "claude"
        assert isinstance(get_model_provider(), ClaudeProvider)
    finally:
        settings.LLM_PROVIDER = previous


def test_retry_succeeds_after_transient_failures() -> None:
    attempts = {"n": 0}

    async def flaky() -> dict:
        attempts["n"] += 1
        if attempts["n"] < 3:
            raise TimeoutError("temporary")
        return {"ok": True}

    assert asyncio.run(retry_generate(flaky, attempts=3, timeout_seconds=2)) == {"ok": True}
    assert attempts["n"] == 3


def test_retry_does_not_retry_auth_errors() -> None:
    class AuthError(Exception):
        status_code = 401

    attempts = {"n": 0}

    async def unauthorized() -> dict:
        attempts["n"] += 1
        raise AuthError("Unauthorized")

    with pytest.raises(AuthError):
        asyncio.run(retry_generate(unauthorized, attempts=3, timeout_seconds=2))
    assert attempts["n"] == 1
    assert is_auth_error(AuthError("Unauthorized"))


def test_retry_raises_after_exhausted_attempts() -> None:
    async def always_fail() -> dict:
        raise RuntimeError("down")

    with pytest.raises(RuntimeError, match="down"):
        asyncio.run(retry_generate(always_fail, attempts=2, timeout_seconds=1))


def test_same_anomalies_scored_by_both_providers() -> None:
    shared = {
        "risk_score": 0.8,
        "risk_factors": ["unknown_counterparty"],
        "explanation": "New vendor.",
    }
    claude = RecordingProvider("claude", shared)
    gemini = RecordingProvider("gemini", shared)
    rows = asyncio.run(compare_providers(CASES, claude, gemini))
    assert len(rows) == 2
    assert claude.calls == 2
    assert gemini.calls == 2
    assert rows[0]["claude"]["risk_score"] == rows[0]["gemini"]["risk_score"]
    assert rows[1]["claude"]["risk_factors"] == rows[1]["gemini"]["risk_factors"]
    assert rows[0]["claude"]["status"] == "answered"
    assert rows[0]["gemini"]["status"] == "answered"


def test_compare_runs_gemini_only_and_stops_after_auth_error() -> None:
    class AuthError(Exception):
        status_code = 401

    class FailingClaude:
        def __init__(self) -> None:
            self.calls = 0

        async def generate_structured(self, prompt: str, schema: dict) -> dict:
            self.calls += 1
            raise AuthError("Unauthorized")

    shared = {
        "risk_score": 0.8,
        "risk_factors": ["unknown_counterparty"],
        "explanation": "New vendor.",
    }
    claude = FailingClaude()
    gemini = RecordingProvider("gemini", shared)
    rows = asyncio.run(compare_providers(CASES, claude, gemini))
    assert claude.calls == 1
    assert gemini.calls == 2
    assert rows[0]["claude"]["status"] == "auth_error"
    assert rows[1]["claude"]["status"] == "skipped"
    assert rows[0]["gemini"]["status"] == "answered"
