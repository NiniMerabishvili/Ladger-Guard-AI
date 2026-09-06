"""Score the same leftover cases with Claude and/or Gemini.

    cd backend
    python -m scripts.compare_providers
"""

import asyncio
from dataclasses import dataclass
from datetime import date

from app.agent.compare import compare_providers
from app.agent.model_provider import ClaudeProvider, GeminiProvider
from app.config import settings


@dataclass
class SampleTx:
    amount: float
    date: date
    description: str
    counterparty: str
    currency: str = "USD"
    source: str = "bank"


SAMPLES = [
    SampleTx(5000.0, date(2026, 9, 1), "UNKNOWN VENDOR WIRE", "ACME LLC"),
    SampleTx(4.50, date(2026, 9, 2), "STARBUCKS STORE 11847", "STARBUCKS"),
    SampleTx(12000.0, date(2026, 9, 3), "PAYROLL DUPLICATE ACH", "PAYROLL CO"),
]


def _cell(result: dict, field: str) -> str:
    if result["status"] == "skipped":
        return "—"
    if field == "risk_score":
        value = result["risk_score"]
        if result["status"] != "answered":
            return f"{value} ({result['status']})"
        return str(value)
    factors = result.get("risk_factors") or []
    return ", ".join(factors) if factors else "[]"


def _summarize(name: str, rows: list[dict], key: str) -> str:
    statuses = [row[key]["status"] for row in rows]
    if all(status == "skipped" for status in statuses):
        return f"{name}: skipped (no key or disabled after auth error)"
    if "answered" in statuses:
        return f"{name}: answered ({statuses.count('answered')} case(s))"
    if "auth_error" in statuses:
        err = next(row[key]["error"] for row in rows if row[key]["status"] == "auth_error")
        return f"{name}: auth error — {err}"
    err = next((row[key]["error"] for row in rows if row[key]["error"]), "unknown")
    return f"{name}: fallback — {err}"


async def main() -> None:
    claude = ClaudeProvider() if settings.ANTHROPIC_API_KEY else None
    gemini = GeminiProvider() if settings.GOOGLE_API_KEY else None

    print("Claude:", "will try" if claude else "skipped (ANTHROPIC_API_KEY empty)")
    print("Gemini:", "will try" if gemini else "skipped (GOOGLE_API_KEY empty)")
    if claude is None and gemini is None:
        print("Set ANTHROPIC_API_KEY and/or GOOGLE_API_KEY in backend/.env")
        return

    rows = await compare_providers(SAMPLES, claude=claude, gemini=gemini)
    print(_summarize("Claude", rows, "claude"))
    print(_summarize("Gemini", rows, "gemini"))
    print()
    print("| Case | Claude risk | Gemini risk | Claude factors | Gemini factors |")
    print("|---|---|---|---|---|")
    for row in rows:
        print(
            f"| {row['case']} | {_cell(row['claude'], 'risk_score')} | "
            f"{_cell(row['gemini'], 'risk_score')} | "
            f"{_cell(row['claude'], 'risk_factors')} | "
            f"{_cell(row['gemini'], 'risk_factors')} |"
        )


if __name__ == "__main__":
    asyncio.run(main())
