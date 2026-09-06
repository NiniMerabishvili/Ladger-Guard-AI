"""Load bank statement and internal ledger CSVs."""

from pathlib import Path

import pandas as pd

from app.core.exceptions import IngestionError
from app.ingestion.normalizer import normalize_transaction
from app.schemas.transaction import TransactionCreate

REQUIRED_COLUMNS = (
    "transaction_id",
    "date",
    "amount",
    "currency",
    "description",
    "counterparty",
)


def load_csv(path: Path) -> pd.DataFrame:
    """Read a CSV and validate that all required columns are present."""
    csv_path = Path(path)
    if not csv_path.is_file():
        raise IngestionError(f"CSV not found: {csv_path}")

    try:
        frame = pd.read_csv(csv_path, dtype=str, keep_default_na=False)
    except Exception as exc:
        raise IngestionError(f"Failed to read CSV: {csv_path}") from exc

    missing = [col for col in REQUIRED_COLUMNS if col not in frame.columns]
    if missing:
        raise IngestionError(f"CSV missing required columns: {', '.join(missing)}")

    return frame


def ingest_csv(path: Path, source: str) -> list[TransactionCreate]:
    """Load a CSV and return normalized TransactionCreate objects."""
    frame = load_csv(path)
    return [normalize_transaction(row.to_dict(), source) for _, row in frame.iterrows()]
