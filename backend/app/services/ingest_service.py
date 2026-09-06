"""Persist normalized CSV rows into the transactions table."""

from pathlib import Path
from uuid import UUID, uuid4

from sqlalchemy.orm import Session

from app.config import _BACKEND_DIR
from app.core.exceptions import IngestionError
from app.db.models import Transaction
from app.ingestion.csv_loader import ingest_csv, ingest_csv_bytes
from app.schemas.transaction import TransactionCreate
from app.services.project_service import clear_project_data, get_project

DEFAULT_BANK_CSV = _BACKEND_DIR / "data" / "bank_statement.csv"
DEFAULT_LEDGER_CSV = _BACKEND_DIR / "data" / "internal_ledger.csv"


def persist_transactions(
    db: Session,
    rows: list[TransactionCreate],
    *,
    project_id: UUID | None = None,
) -> list[Transaction]:
    """Insert normalized rows as unmatched transactions."""
    created: list[Transaction] = []
    for row in rows:
        tx = Transaction(
            id=uuid4(),
            project_id=project_id,
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


def _counts(bank_rows: list[TransactionCreate], ledger_rows: list[TransactionCreate]) -> dict[str, int]:
    return {
        "bank_count": len(bank_rows),
        "ledger_count": len(ledger_rows),
        "total": len(bank_rows) + len(ledger_rows),
    }


def ingest_files(
    db: Session,
    *,
    bank_path: Path | None = None,
    ledger_path: Path | None = None,
    project_id: UUID | None = None,
) -> dict[str, int]:
    """Load default (or provided) CSVs, normalize, and write to the DB."""
    bank_rows = ingest_csv(bank_path or DEFAULT_BANK_CSV, "bank")
    ledger_rows = ingest_csv(ledger_path or DEFAULT_LEDGER_CSV, "ledger")
    persist_transactions(db, bank_rows, project_id=project_id)
    persist_transactions(db, ledger_rows, project_id=project_id)
    return _counts(bank_rows, ledger_rows)


def ingest_uploads(
    db: Session,
    *,
    bank_bytes: bytes,
    ledger_bytes: bytes,
    bank_name: str = "bank_statement.csv",
    ledger_name: str = "internal_ledger.csv",
    project_id: UUID | None = None,
    replace_existing: bool = True,
) -> dict[str, int | str]:
    """Ingest two uploaded CSV payloads into a project workspace."""
    if project_id is None:
        raise IngestionError("project_id is required")
    project = get_project(db, project_id)
    if project is None:
        raise IngestionError("Project not found")

    bank_rows = ingest_csv_bytes(bank_bytes, "bank", label=bank_name)
    ledger_rows = ingest_csv_bytes(ledger_bytes, "ledger", label=ledger_name)
    if not bank_rows and not ledger_rows:
        raise IngestionError("Both CSVs have no data rows")
    if replace_existing:
        clear_project_data(db, project_id)
    persist_transactions(db, bank_rows, project_id=project_id)
    persist_transactions(db, ledger_rows, project_id=project_id)

    project.bank_filename = bank_name
    project.ledger_filename = ledger_name
    project.status = "open"
    db.add(project)
    db.flush()

    counts = _counts(bank_rows, ledger_rows)
    return {**counts, "project_id": str(project_id)}
