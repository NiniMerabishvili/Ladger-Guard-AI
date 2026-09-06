"""Tests for date parsing, currency conversion, and description cleanup."""

from datetime import date

import pytest

from app.core.exceptions import IngestionError
from app.ingestion.normalizer import (
    clean_description,
    convert_amount_to_usd,
    normalize_transaction,
    parse_date,
)


@pytest.mark.parametrize(
    ("raw", "expected"),
    [
        ("2026-09-01", date(2026, 9, 1)),
        ("09/01/2026", date(2026, 9, 1)),
        ("1 Sep 2026", date(2026, 9, 1)),
        ("September 1, 2026", date(2026, 9, 1)),
    ],
)
def test_parse_date_format_variants(raw: str, expected: date) -> None:
    assert parse_date(raw) == expected


def test_parse_date_rejects_invalid() -> None:
    with pytest.raises(IngestionError, match="Invalid date"):
        parse_date("not-a-date")


def test_convert_amount_to_usd() -> None:
    assert convert_amount_to_usd(100, "EUR") == (108.0, "USD")
    assert convert_amount_to_usd(100, "GBP") == (127.0, "USD")
    assert convert_amount_to_usd("50.50", "usd") == (50.50, "USD")


def test_convert_amount_rejects_unknown_currency() -> None:
    with pytest.raises(IngestionError, match="Unsupported currency"):
        convert_amount_to_usd(10, "JPY")


@pytest.mark.parametrize(
    ("raw", "expected"),
    [
        ("acme corp 847291 *POS", "ACME CORP"),
        ("ACME CORP REF#12345", "ACME CORP"),
        ("  payment 123456789 merchant  ", "PAYMENT MERCHANT"),
        ("Starbucks *POS", "STARBUCKS"),
    ],
)
def test_clean_description_strips_ids_and_suffixes(raw: str, expected: str) -> None:
    assert clean_description(raw) == expected


def test_normalize_transaction_sets_source_and_iso_date(sample_bank_row: dict) -> None:
    tx = normalize_transaction(
        {**sample_bank_row, "currency": "EUR", "description": "acme corp REF#99999"},
        source="bank",
    )
    assert tx.source == "bank"
    assert tx.date == date(2026, 9, 1)
    assert tx.amount == 108.0
    assert tx.currency == "USD"
    assert tx.description == "ACME CORP"
    assert tx.counterparty == "ACME CORP"
