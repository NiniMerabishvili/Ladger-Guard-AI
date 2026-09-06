"""Log every embedding/LLM call and keep a running spend total.

Rates are mock portfolio figures, not live vendor prices.
"""

from dataclasses import dataclass

# Mock USD charged per logged call (tokens_or_calls is treated as call count).
MOCK_USD_PER_CALL: dict[str, float] = {
    "local": 0.0,
    "sentence-transformers": 0.0,
    "openai": 0.0001,
    "claude": 0.003,
    "anthropic": 0.003,
    "gemini": 0.0002,
    "google": 0.0002,
}

# Assumption used on the dashboard — not a measured production figure.
MANUAL_LABOR_USD_PER_AUTO_MATCH = 2.50


@dataclass
class CostEntry:
    provider: str
    model: str
    tokens_or_calls: int
    usd: float


_entries: list[CostEntry] = []


def reset() -> None:
    _entries.clear()


def log_call(provider: str, model: str, tokens_or_calls: int) -> None:
    calls = max(int(tokens_or_calls), 1)
    rate = MOCK_USD_PER_CALL.get(provider.lower(), 0.001)
    _entries.append(
        CostEntry(
            provider=provider,
            model=model,
            tokens_or_calls=calls,
            usd=round(rate * calls, 6),
        )
    )


def get_estimated_cost_usd() -> float:
    return round(sum(item.usd for item in _entries), 6)


def get_call_log() -> list[CostEntry]:
    return list(_entries)
