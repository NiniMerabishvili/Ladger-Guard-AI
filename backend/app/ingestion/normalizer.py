"""Date, currency, and description cleanup."""

import re
from datetime import date

from dateutil import parser as date_parser

from app.core.exceptions import IngestionError
from app.schemas.transaction import TransactionCreate

# Mock FX rates to USD. Production would need a real-time FX API.
FX_RATES_TO_USD: dict[str, float] = {
    "USD": 1.0,
    "EUR": 1.08,
    "GBP": 1.27,
}

_LONG_NUMERIC_ID_RE = re.compile(r"\d{6,}")
_MERCHANT_SUFFIX_RE = re.compile(
    r"(?:\s+(?:REF#\S+|\*POS|\*PURCHASE|\*ACH|POS))+$",
    re.IGNORECASE,
)
_WHITESPACE_RE = re.compile(r"\s+")


def parse_date(value: object) -> date:
    """Parse a date string into a date (ISO 8601 when serialized)."""
    if value is None or (isinstance(value, str) and not value.strip()):
        raise IngestionError("Missing date")
    try:
        parsed = date_parser.parse(str(value).strip())
    except (ValueError, OverflowError, TypeError) as exc:
        raise IngestionError(f"Invalid date: {value}") from exc
    return parsed.date()


def convert_amount_to_usd(amount: object, currency: object) -> tuple[float, str]:
    """Convert amount to USD using the mock rate table. Returns (usd_amount, 'USD')."""
    code = str(currency or "").strip().upper()
    if code not in FX_RATES_TO_USD:
        raise IngestionError(f"Unsupported currency: {currency}")
    try:
        raw_amount = float(str(amount).replace(",", "").strip())
    except (TypeError, ValueError) as exc:
        raise IngestionError(f"Invalid amount: {amount}") from exc
    usd_amount = round(raw_amount * FX_RATES_TO_USD[code], 2)
    return usd_amount, "USD"


def clean_description(description: object) -> str:
    """Strip long IDs and merchant suffixes, then normalize case."""
    text = str(description or "")
    text = _LONG_NUMERIC_ID_RE.sub("", text)
    text = _MERCHANT_SUFFIX_RE.sub("", text)
    return _WHITESPACE_RE.sub(" ", text).strip().upper()


def normalize_transaction(raw: dict, source: str) -> TransactionCreate:
    """Normalize a raw CSV row into a TransactionCreate object."""
    amount, currency = convert_amount_to_usd(raw.get("amount"), raw.get("currency"))
    counterparty = raw.get("counterparty")
    counterparty_text = str(counterparty).strip() if counterparty is not None else ""
    return TransactionCreate(
        source=source,
        date=parse_date(raw.get("date")),
        amount=amount,
        currency=currency,
        description=clean_description(raw.get("description")),
        counterparty=counterparty_text.upper() or None,
    )


def normalize_rows(rows: list[dict], source: str) -> list[TransactionCreate]:
    """Normalize a list of raw rows into TransactionCreate objects."""
    return [normalize_transaction(row, source) for row in rows]
