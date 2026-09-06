"""Ingest service: CSV → normalized Transaction rows."""

from datetime import date
from pathlib import Path
from unittest.mock import MagicMock

from app.schemas.transaction import TransactionCreate
from app.services.ingest_service import ingest_files, persist_transactions


def test_persist_transactions_marks_rows_unmatched() -> None:
    db = MagicMock()
    rows = [
        TransactionCreate(
            source="bank",
            date=date(2026, 9, 1),
            amount=10.0,
            currency="USD",
            description="COFFEE",
            counterparty="CAFE",
        )
    ]
    created = persist_transactions(db, rows)
    assert len(created) == 1
    assert created[0].status == "unmatched"
    assert created[0].source == "bank"
    db.add.assert_called()
    db.flush.assert_called_once()


def test_ingest_files_reads_both_csvs(tmp_path: Path) -> None:
    bank = tmp_path / "bank.csv"
    ledger = tmp_path / "ledger.csv"
    header = "transaction_id,date,amount,currency,description,counterparty\n"
    bank.write_text(
        header + "b1,2026-09-01,4.50,USD,STARBUCKS STORE,STARBUCKS\n",
        encoding="utf-8",
    )
    ledger.write_text(
        header + "l1,2026-09-01,4.50,USD,Starbucks Card,STARBUCKS\n",
        encoding="utf-8",
    )
    db = MagicMock()
    result = ingest_files(db, bank_path=bank, ledger_path=ledger)
    assert result == {"bank_count": 1, "ledger_count": 1, "total": 2}
    assert db.add.call_count == 2
