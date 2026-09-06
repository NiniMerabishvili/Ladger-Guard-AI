"""Domain and HTTP exception types."""


class ReconciliationError(Exception):
    """Base error for the reconciliation pipeline."""


class IngestionError(ReconciliationError):
    """CSV load or validation failed."""


class SchemaValidationError(ReconciliationError):
    """LLM structured output failed schema validation."""


class TransactionNotFoundError(ReconciliationError):
    """No transaction exists for the given id."""


class ReviewActionError(ReconciliationError):
    """Human review payload is invalid."""
