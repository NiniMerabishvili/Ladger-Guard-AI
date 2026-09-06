"""LLM anomaly scoring agent with structured JSON output."""

from pydantic import BaseModel, Field, ValidationError

from app.agent.model_provider import ModelProvider, get_model_provider
from app.agent.prompts import ALLOWED_RISK_FACTORS, ANOMALY_SCHEMA, build_anomaly_prompt
from app.config import settings
from app.services.cost_tracker import log_call

FALLBACK_EXPLANATION = "Agent output could not be validated"
FALLBACK_RISK_SCORE = 0.1
FLAG_MEMORY_THRESHOLD = 0.5


class RunContext:
    """In-memory, run-scoped session memory for flagged counterparties."""

    def __init__(self, llm_budget: int | None = None) -> None:
        self.flagged_counterparties: dict[str, list[str]] = {}
        # After one auth failure, skip further LLM calls for this run.
        self.llm_unavailable: bool = False
        budget = settings.LLM_MAX_PER_RUN if llm_budget is None else llm_budget
        self.llm_budget: int = max(0, int(budget))

    def note_flag(self, counterparty: str, reason: str) -> None:
        self.flagged_counterparties.setdefault(counterparty, []).append(reason)

    def get_prior_context(self, counterparty: str) -> str | None:
        prior = self.flagged_counterparties.get(counterparty)
        return f"Note: this counterparty was already flagged for: {prior}" if prior else None

    def take_llm_slot(self) -> bool:
        if self.llm_unavailable or self.llm_budget <= 0:
            return False
        self.llm_budget -= 1
        return True


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


def heuristic_score(transaction: object, context: RunContext | None = None) -> dict:
    """Instant local risk score — used for most leftovers so reconcile stays fast."""
    amount = abs(float(getattr(transaction, "amount", 0) or 0))
    counterparty = (getattr(transaction, "counterparty", None) or "").strip()
    description = (getattr(transaction, "description", None) or "").strip()
    factors: list[str] = []
    score = 0.12
    notes: list[str] = []

    if amount >= 5000:
        factors.append("unusual_amount")
        score += 0.45
        notes.append(f"Large unmatched amount ({amount:.2f}).")
    elif amount >= 1000:
        factors.append("unusual_amount")
        score += 0.25
        notes.append(f"Elevated unmatched amount ({amount:.2f}).")

    known_hints = (
        "STARBUCKS",
        "UBER",
        "AMAZON",
        "GOOGLE",
        "MICROSOFT",
        "SLACK",
        "LINKEDIN",
        "AWS",
        "GITHUB",
        "ZOOM",
        "ADOBE",
        "NETFLIX",
        "SPOTIFY",
        "PAYPAL",
        "STRIPE",
    )
    blob = f"{counterparty} {description}".upper()
    if not counterparty or counterparty.upper() in {"UNKNOWN", "N/A", "NONE"}:
        factors.append("unknown_counterparty")
        score += 0.3
        notes.append("Missing or unknown counterparty.")
    elif not any(hint in blob for hint in known_hints) and amount >= 500:
        factors.append("unknown_counterparty")
        score += 0.2
        notes.append("Counterparty is not a common known merchant.")

    if context and counterparty:
        prior = context.get_prior_context(counterparty)
        if prior:
            score += 0.15
            notes.append(prior)

    score = min(0.95, round(score, 2))
    if not notes:
        notes.append("Routine unmatched line; low heuristic risk.")
    # Deduplicate while preserving order
    seen: set[str] = set()
    unique_factors: list[str] = []
    for factor in factors:
        if factor not in seen and factor in ALLOWED_RISK_FACTORS:
            seen.add(factor)
            unique_factors.append(factor)
    return {
        "risk_score": score,
        "risk_factors": unique_factors,
        "explanation": " ".join(notes),
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
    *,
    use_llm: bool | None = None,
) -> dict:
    """Score an unmatched transaction.

    By default only a small budget of live LLM calls run per reconcile; everything
    else uses ``heuristic_score`` so Upload & run finishes in a few seconds.
    """
    from app.agent.model_provider import is_auth_error

    prefer_llm = context.take_llm_slot() if use_llm is None else use_llm
    if not prefer_llm or context.llm_unavailable:
        result = heuristic_score(transaction, context)
        _remember_if_flagged(transaction, context, result)
        return result

    provider = provider or get_model_provider()
    counterparty = getattr(transaction, "counterparty", None)
    prior = context.get_prior_context(str(counterparty)) if counterparty else None
    prompt = build_anomaly_prompt(transaction, prior)

    try:
        raw = await provider.generate_structured(prompt, ANOMALY_SCHEMA)
        result = validate_anomaly_output(raw)
        log_call(settings.LLM_PROVIDER, getattr(provider, "model", settings.LLM_PROVIDER), 1)
    except (ValidationError, ValueError, TypeError, KeyError):
        # Untrusted structured output → never auto-flag from a bad schema.
        return fallback_anomaly()
    except Exception as exc:
        if is_auth_error(exc):
            context.llm_unavailable = True
        result = heuristic_score(transaction, context)

    _remember_if_flagged(transaction, context, result)
    return result
