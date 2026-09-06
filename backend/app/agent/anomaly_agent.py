"""LLM anomaly scoring agent with structured JSON output."""

from pydantic import BaseModel, Field, ValidationError

from app.agent.model_provider import ModelProvider, get_model_provider
from app.config import settings
from app.services.cost_tracker import log_call
from app.agent.prompts import ALLOWED_RISK_FACTORS, ANOMALY_SCHEMA, build_anomaly_prompt

FALLBACK_EXPLANATION = "Agent output could not be validated"
FALLBACK_RISK_SCORE = 0.1
FLAG_MEMORY_THRESHOLD = 0.5


class RunContext:
    """In-memory, run-scoped session memory for flagged counterparties."""

    def __init__(self) -> None:
        self.flagged_counterparties: dict[str, list[str]] = {}

    def note_flag(self, counterparty: str, reason: str) -> None:
        self.flagged_counterparties.setdefault(counterparty, []).append(reason)

    def get_prior_context(self, counterparty: str) -> str | None:
        prior = self.flagged_counterparties.get(counterparty)
        return f"Note: this counterparty was already flagged for: {prior}" if prior else None


class AnomalyOutput(BaseModel):
    risk_score: float = Field(ge=0, le=1)
    risk_factors: list[str]
    explanation: str

    def model_post_init(self, _context: object) -> None:
        unknown = set(self.risk_factors) - ALLOWED_RISK_FACTORS
        if unknown:
            raise ValueError(f"Unknown risk_factors: {unknown}")


def fallback_anomaly() -> dict:
    """Low-confidence result used when the LLM output cannot be trusted."""
    return {
        "risk_score": FALLBACK_RISK_SCORE,
        "risk_factors": [],
        "explanation": FALLBACK_EXPLANATION,
    }


def validate_anomaly_output(payload: object) -> dict:
    parsed = AnomalyOutput.model_validate(payload)
    return parsed.model_dump()


def _remember_if_flagged(transaction: object, context: RunContext, result: dict) -> None:
    counterparty = getattr(transaction, "counterparty", None)
    if not counterparty:
        return
    if result["risk_score"] >= FLAG_MEMORY_THRESHOLD or result["risk_factors"]:
        context.note_flag(str(counterparty), result["explanation"])


async def score_anomaly(
    transaction: object,
    context: RunContext,
    provider: ModelProvider | None = None,
) -> dict:
    """Call the LLM with a schema-constrained prompt and return structured output.

    Invalid or failed LLM output becomes a low-confidence fallback — never a crash
    and never an overconfident flag.
    """
    provider = provider or get_model_provider()
    counterparty = getattr(transaction, "counterparty", None)
    prior = context.get_prior_context(str(counterparty)) if counterparty else None
    prompt = build_anomaly_prompt(transaction, prior)

    try:
        raw = await provider.generate_structured(prompt, ANOMALY_SCHEMA)
        result = validate_anomaly_output(raw)
        log_call(settings.LLM_PROVIDER, getattr(provider, "model", settings.LLM_PROVIDER), 1)
    except (ValidationError, ValueError, TypeError, KeyError, Exception):
        return fallback_anomaly()

    _remember_if_flagged(transaction, context, result)
    return result
