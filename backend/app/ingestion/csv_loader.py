"""Load bank statement and internal ledger CSVs."""

from io import BytesIO, StringIO
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


def _validate_frame(frame: pd.DataFrame, label: str) -> pd.DataFrame:
    missing = [col for col in REQUIRED_COLUMNS if col not in frame.columns]
    if missing:
        raise IngestionError(f"{label} missing required columns: {', '.join(missing)}")
    return frame


def load_csv(path: Path) -> pd.DataFrame:
    """Read a CSV and validate that all required columns are present."""
    csv_path = Path(path)
    if not csv_path.is_file():
        raise IngestionError(f"CSV not found: {csv_path}")

    try:
        frame = pd.read_csv(csv_path, dtype=str, keep_default_na=False)
    except Exception as exc:
        raise IngestionError(f"Failed to read CSV: {csv_path}") from exc

    return _validate_frame(frame, str(csv_path))


def load_csv_bytes(content: bytes, label: str = "upload") -> pd.DataFrame:
    """Parse an uploaded CSV body into a validated frame."""
    if not content.strip():
        raise IngestionError(f"{label} is empty")
    try:
        text = content.decode("utf-8-sig")
        frame = pd.read_csv(StringIO(text), dtype=str, keep_default_na=False)
    except UnicodeDecodeError:
        try:
            frame = pd.read_csv(BytesIO(content), dtype=str, keep_default_na=False)
        except Exception as exc:
            raise IngestionError(f"Failed to read {label}") from exc
    except Exception as exc:
        raise IngestionError(f"Failed to read {label}") from exc
    return _validate_frame(frame, label)


def rows_from_frame(frame: pd.DataFrame, source: str) -> list[TransactionCreate]:
    return [normalize_transaction(row.to_dict(), source) for _, row in frame.iterrows()]


def ingest_csv(path: Path, source: str) -> list[TransactionCreate]:
    """Load a CSV and return normalized TransactionCreate objects."""
    return rows_from_frame(load_csv(path), source)


def ingest_csv_bytes(
    content: bytes,
    source: str,
    label: str | None = None,
) -> list[TransactionCreate]:
    """Load an uploaded CSV and return normalized TransactionCreate objects."""
    return rows_from_frame(load_csv_bytes(content, label or source), source)
