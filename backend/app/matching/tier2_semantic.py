"""Tier 2 — embeddings + semantic search (in-memory for a reconcile run)."""

from dataclasses import dataclass
from datetime import date
from uuid import UUID

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.db.models import Transaction
from app.matching.embedding_provider import EmbeddingProvider, get_embedding_provider
from app.matching.tier1_rules import MatchResult

SIMILARITY_THRESHOLD = 0.85
AMOUNT_TOLERANCE_PCT = 0.03
DATE_WINDOW_DAYS = 3
SEARCH_LIMIT = 5


@dataclass
class SemanticCandidate:
    id: UUID
    description: str
    amount: float
    date: date
    similarity: float


def _as_float(amount: object) -> float:
    return float(amount)  # type: ignore[arg-type]


def opposite_source(source: str) -> str:
    return "ledger" if source == "bank" else "bank"


def _dot(a: list[float], b: list[float]) -> float:
    """Cosine similarity for L2-normalized vectors (local MiniLM uses normalize_embeddings)."""
    size = min(len(a), len(b))
    return sum(a[i] * b[i] for i in range(size))


def amount_and_date_close(
    query_tx: object,
    candidate: SemanticCandidate,
    amount_tol_pct: float = AMOUNT_TOLERANCE_PCT,
    date_window_days: int = DATE_WINDOW_DAYS,
) -> bool:
    """Wider tolerance than Tier 1: ±3% amount, ±3 days."""
    query_amount = _as_float(query_tx.amount)
    amount_ok = abs(query_amount - candidate.amount) <= abs(query_amount) * amount_tol_pct
    date_ok = abs((query_tx.date - candidate.date).days) <= date_window_days
    return amount_ok and date_ok


def decide_semantic_match(query_tx: object, candidates: list[SemanticCandidate]) -> MatchResult:
    """Apply similarity + amount/date gates. No embedding or DB calls."""
    if not candidates:
        return MatchResult(matched=False)
    best = max(candidates, key=lambda row: row.similarity)
    if best.similarity > SIMILARITY_THRESHOLD and amount_and_date_close(query_tx, best):
        return MatchResult(
            matched=True,
            confidence=best.similarity,
            method="semantic_match",
            matched_id=best.id,
        )
    return MatchResult(matched=False)


def store_embedding(
    db: Session,
    transaction: Transaction,
    provider: EmbeddingProvider,
) -> list[float]:
    """Compute an embedding for a Tier 1 leftover and write it to pgvector."""
    vector = provider.embed(transaction.description)
    transaction.embedding = vector
    db.add(transaction)
    return vector


def ensure_embeddings(
    db: Session,
    rows: list[Transaction],
    provider: EmbeddingProvider,
    *,
    flush: bool = True,
) -> int:
    """Batch-embed any rows missing vectors (one encode call for the whole set)."""
    missing = [row for row in rows if row.embedding is None]
    if not missing:
        return 0
    vectors = provider.embed_many([row.description for row in missing])
    for row, vector in zip(missing, vectors, strict=True):
        row.embedding = vector
        db.add(row)
    if flush:
        db.flush()
    return len(missing)


def embed_unmatched_transactions(db: Session, provider: EmbeddingProvider | None = None) -> int:
    """Embed unmatched rows that do not yet have a vector."""
    provider = provider or get_embedding_provider()
    rows = list(
        db.scalars(
            select(Transaction).where(
                Transaction.status == "unmatched",
                Transaction.embedding.is_(None),
            )
        ).all()
    )
    return ensure_embeddings(db, rows, provider)


def find_similar_in_memory(
    query_embedding: list[float],
    candidates: list[Transaction],
    *,
    exclude_id: UUID | None = None,
    limit: int = SEARCH_LIMIT,
) -> list[SemanticCandidate]:
    """Rank open opposite-source rows by cosine similarity without per-row SQL."""
    scored: list[SemanticCandidate] = []
    for row in candidates:
        if exclude_id is not None and row.id == exclude_id:
            continue
        embedding = row.embedding
        if embedding is None:
            continue
        scored.append(
            SemanticCandidate(
                id=row.id,
                description=row.description,
                amount=_as_float(row.amount),
                date=row.date,
                similarity=_dot(query_embedding, list(embedding)),
            )
        )
    scored.sort(key=lambda item: item.similarity, reverse=True)
    return scored[:limit]


def search_similar(
    db: Session,
    query_embedding: list[float],
    opposite: str,
    *,
    project_id: UUID | None = None,
    exclude_id: UUID | None = None,
    limit: int = SEARCH_LIMIT,
) -> list[SemanticCandidate]:
    """Nearest unmatched rows of the opposite source (cosine similarity via pgvector)."""
    distance = Transaction.embedding.cosine_distance(query_embedding)
    similarity = (1 - distance).label("similarity")
    stmt = (
        select(
            Transaction.id,
            Transaction.description,
            Transaction.amount,
            Transaction.date,
            similarity,
        )
        .where(Transaction.source == opposite)
        .where(Transaction.status == "unmatched")
        .where(Transaction.embedding.is_not(None))
        .order_by(distance)
        .limit(limit)
    )
    if project_id is not None:
        stmt = stmt.where(Transaction.project_id == project_id)
    if exclude_id is not None:
        stmt = stmt.where(Transaction.id != exclude_id)

    return [
        SemanticCandidate(
            id=row.id,
            description=row.description,
            amount=_as_float(row.amount),
            date=row.date,
            similarity=float(row.similarity),
        )
        for row in db.execute(stmt).all()
    ]


def try_semantic_match(
    transaction: Transaction,
    db: Session,
    provider: EmbeddingProvider | None = None,
    *,
    ledger_pool: list[Transaction] | None = None,
) -> MatchResult:
    """Find a semantic match among unmatched transactions of the opposite source."""
    provider = provider or get_embedding_provider()
    query_embedding = transaction.embedding or store_embedding(db, transaction, provider)
    if ledger_pool is not None:
        candidates = find_similar_in_memory(
            query_embedding,
            ledger_pool,
            exclude_id=transaction.id,
        )
    else:
        candidates = search_similar(
            db,
            query_embedding,
            opposite_source(transaction.source),
            project_id=transaction.project_id,
            exclude_id=transaction.id,
        )
    return decide_semantic_match(transaction, candidates)
