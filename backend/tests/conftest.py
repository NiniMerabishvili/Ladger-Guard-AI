"""Shared pytest fixtures."""

import pytest


@pytest.fixture
def sample_bank_row() -> dict:
    return {
        "transaction_id": "bank-001",
        "date": "2026-09-01",
        "amount": "100.00",
        "currency": "USD",
        "description": "ACME CORP POS",
        "counterparty": "ACME CORP",
    }
