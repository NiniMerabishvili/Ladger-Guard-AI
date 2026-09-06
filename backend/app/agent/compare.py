"""Run the same anomalies through one or both ModelProviders."""

from app.agent.anomaly_agent import (
    RunContext,
    fallback_anomaly,
    validate_anomaly_output,
    _remember_if_flagged,
)
from app.agent.model_provider import ModelProvider, is_auth_error
from app.agent.prompts import ANOMALY_SCHEMA, build_anomaly_prompt


def _skipped() -> dict:
    return {
        "risk_score": None,
        "risk_factors": None,
        "explanation": None,
        "status": "skipped",
        "error": None,
    }


async def _score_one(
    case: object,
    context: RunContext,
    provider: ModelProvider | None,
) -> dict:
    if provider is None:
        return _skipped()

    counterparty = getattr(case, "counterparty", None)
    prior = context.get_prior_context(str(counterparty)) if counterparty else None
    prompt = build_anomaly_prompt(case, prior)
    try:
        raw = await provider.generate_structured(prompt, ANOMALY_SCHEMA)
        result = validate_anomaly_output(raw)
    except Exception as exc:
        fallback = fallback_anomaly()
        status = "auth_error" if is_auth_error(exc) else "fallback"
        return {
            **fallback,
            "status": status,
            "error": f"{type(exc).__name__}: {exc}"[:240],
        }

    _remember_if_flagged(case, context, result)
    return {**result, "status": "answered", "error": None}


async def compare_providers(
    cases: list[object],
    claude: ModelProvider | None = None,
    gemini: ModelProvider | None = None,
) -> list[dict]:
    """Score each case with whichever providers are given (separate run memory).

    After an auth error, that provider is skipped for the rest of the run.
    """
    rows: list[dict] = []
    claude_ctx = RunContext()
    gemini_ctx = RunContext()
    use_claude = claude
    use_gemini = gemini
    for case in cases:
        label = getattr(case, "description", str(case))
        claude_result = await _score_one(case, claude_ctx, use_claude)
        gemini_result = await _score_one(case, gemini_ctx, use_gemini)
        if claude_result["status"] == "auth_error":
            use_claude = None
        if gemini_result["status"] == "auth_error":
            use_gemini = None
        rows.append({"case": label, "claude": claude_result, "gemini": gemini_result})
    return rows
