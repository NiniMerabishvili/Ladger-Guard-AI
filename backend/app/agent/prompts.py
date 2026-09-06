"""Prompts and JSON schema for the anomaly scoring agent."""

ANOMALY_SCHEMA = {
    "type": "object",
    "properties": {
        "risk_score": {"type": "number", "minimum": 0, "maximum": 1},
        "risk_factors": {
            "type": "array",
            "items": {
                "enum": [
                    "duplicate_payment",
                    "unusual_amount",
                    "off_hours",
                    "unknown_counterparty",
                    "currency_mismatch",
                ]
            },
        },
        "explanation": {"type": "string"},
    },
    "required": ["risk_score", "risk_factors", "explanation"],
}

ALLOWED_RISK_FACTORS = frozenset(
    ANOMALY_SCHEMA["properties"]["risk_factors"]["items"]["enum"]
)

ANOMALY_SYSTEM_PROMPT = """You are an anomaly scoring agent for financial reconciliation.
If you cannot justify with specific evidence, set risk_score low and explain why, rather than guessing.
Return only structured JSON matching the provided schema.
"""


def build_anomaly_prompt(transaction: object, prior_context: str | None) -> str:
    counterparty = getattr(transaction, "counterparty", None) or "unknown"
    lines = [
        "Score this unmatched transaction for reconciliation risk.",
        f"- source: {getattr(transaction, 'source', 'unknown')}",
        f"- date: {getattr(transaction, 'date', 'unknown')}",
        f"- amount: {getattr(transaction, 'amount', 'unknown')}",
        f"- currency: {getattr(transaction, 'currency', 'unknown')}",
        f"- description: {getattr(transaction, 'description', '')}",
        f"- counterparty: {counterparty}",
    ]
    if prior_context:
        lines.append(prior_context)
    lines.append(
        "If you cannot justify with specific evidence, set risk_score low and explain why, "
        "rather than guessing."
    )
    return "\n".join(lines)
