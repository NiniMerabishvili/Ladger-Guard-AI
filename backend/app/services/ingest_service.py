"""Persist normalized CSV rows into the transactions table."""

from pathlib import Path
from uuid import uuid4

from sqlalchemy.orm import Session

from app.config import _BACKEND_DIR
from app.db.models import Transaction
from app.ingestion.csv_loader import ingest_csv
from app.schemas.transaction import TransactionCreate

DEFAULT_BANK_CSV = _BACKEND_DIR / "data" / "bank_statement.csv"
DEFAULT_LEDGER_CSV = _BACKEND_DIR / "data" / "internal_ledger.csv"


def persist_transactions(db: Session, rows: list[TransactionCreate]) -> list[Transaction]:
    """Insert normalized rows as unmatched transactions."""
    created: list[Transaction] = []
    for row in rows:
        tx = Transaction(
            id=uuid4(),
            source=row.source,
            date=row.date,
            amount=row.amount,
            currency=row.currency,
            description=row.description,
            counterparty=row.counterparty,
            status="unmatched",
        )
        db.add(tx)
        created.append(tx)
    db.flush()
    return created


def ingest_files(
    db: Session,
    *,
    bank_path: Path | None = None,
    ledger_path: Path | None = None,
) -> dict[str, int]:
    """Load default (or provided) CSVs, normalize, and write to the DB."""
    bank_rows = ingest_csv(bank_path or DEFAULT_BANK_CSV, "bank")
    ledger_rows = ingest_csv(ledger_path or DEFAULT_LEDGER_CSV, "ledger")
    bank_created = persist_transactions(db, bank_rows)
    ledger_created = persist_transactions(db, ledger_rows)
    return {
        "bank_count": len(bank_created),
        "ledger_count": len(ledger_created),
        "total": len(bank_created) + len(ledger_created),
    }
