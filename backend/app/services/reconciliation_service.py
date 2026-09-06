"""Orchestrates Tier1 → Tier2 → Anomaly Agent with idempotent skips."""

from __future__ import annotations

import asyncio
from collections.abc import Awaitable, Callable
from typing import TYPE_CHECKING, Any
from uuid import UUID, uuid4

from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.config import settings
from app.db.models import Decision, Transaction
from app.matching.tier1_rules import AmountIndex, MatchResult
from app.matching.tier2_semantic import ensure_embeddings, try_semantic_match
from app.services.audit_service import record_decision
from app.services.n8n_service import build_n8n_payload, should_notify
from app.services.review_service import apply_review_threshold

if TYPE_CHECKING:
    from app.matching.embedding_provider import EmbeddingProvider

# Once the pipeline (or a human) has decided, re-runs must not touch the row again.
RESOLVED_STATUSES = frozenset({"matched", "flagged", "pending_review"})

ScoreFn = Callable[[Transaction, Any], Awaitable[dict[str, Any]]]


def is_open_for_matching(transaction: Transaction) -> bool:
    """Only unmatched rows are eligible for another matching pass."""
    return transaction.status == "unmatched"


def count_decisions(db: Session) -> int:
    return int(db.scalar(select(func.count()).select_from(Decision)) or 0)


def _apply_match(
    db: Session,
    bank_tx: Transaction,
    *,
    matched_id: UUID,
    decision: str,
    method: str,
    confidence: float,
    reasoning: dict[str, Any] | None,
    matching_run_id: UUID,
    model_used: str | None = None,
    ledger_by_id: dict[UUID, Transaction] | None = None,
    flush: bool = False,
) -> Decision:
    row = record_decision(
        db,
        transaction_id=bank_tx.id,
        decision=decision,
        method=method,
        confidence=confidence,
        matched_transaction_id=matched_id,
        reasoning=reasoning,
        model_used=model_used,
        matching_run_id=matching_run_id,
        flush=flush,
    )
    bank_tx.status = decision
    db.add(bank_tx)
    ledger = None
    if ledger_by_id is not None:
        ledger = ledger_by_id.get(matched_id)
    if ledger is None:
        ledger = db.get(Transaction, matched_id)
    if ledger is not None and is_open_for_matching(ledger):
        ledger.status = "matched" if decision == "matched" else ledger.status
        if decision == "matched":
            db.add(ledger)
    if flush:
        db.flush()
    return row


def _apply_agent_outcome(
    db: Session,
    bank_tx: Transaction,
    agent_result: dict[str, Any],
    matching_run_id: UUID,
    *,
    flush: bool = False,
) -> Decision:
    risk = float(agent_result["risk_score"])
    confidence = risk
    intended = "flagged" if risk >= settings.REVIEW_CONFIDENCE_THRESHOLD else "matched"
    decision = apply_review_threshold(confidence, intended=intended)
    row = record_decision(
        db,
        transaction_id=bank_tx.id,
        decision=decision,
        method="llm_agent",
        confidence=confidence,
        reasoning=agent_result,
        model_used=settings.LLM_PROVIDER,
        matching_run_id=matching_run_id,
        flush=flush,
    )
    bank_tx.status = decision
    db.add(bank_tx)
    if flush:
        db.flush()
    return row


async def _default_score(transaction: Transaction, context: Any) -> dict[str, Any]:
    # Lazy import avoids circular: services → reconciliation → agent → services.cost_tracker
    from app.agent.anomaly_agent import score_anomaly

    return await score_anomaly(transaction, context)


def run_reconciliation(
    db: Session,
    run_id: UUID | None = None,
    *,
    project_id: UUID | None = None,
    score_fn: ScoreFn | None = None,
    embedding_provider: EmbeddingProvider | None = None,
    skip_semantic: bool = False,
    notify: bool = True,
    bank_rows: list[Transaction] | None = None,
    ledger_rows: list[Transaction] | None = None,
) -> dict[str, Any]:
    """Run Tier1 → Tier2 → Agent.

    Transactions that are already matched / flagged / pending_review are skipped.
    Every decision row carries ``matching_run_id``. Running twice on the same data
    must not increase the decisions count.

    ``bank_rows`` / ``ledger_rows`` let unit tests inject in-memory transactions
    without SQLAlchemy select plumbing.

    ClickUp/n8n payloads are collected in ``notify_payloads`` so the HTTP route can
    send them in the background after commit (keeps reconcile itself fast).
    """
    from app.agent.anomaly_agent import RunContext, heuristic_score

    matching_run_id = run_id or uuid4()
    score = score_fn or _default_score
    context = RunContext()
    # One provider for the whole run — avoid reloading SentenceTransformer per row.
    provider = embedding_provider
    if provider is None and not skip_semantic:
        from app.matching.embedding_provider import get_embedding_provider

        provider = get_embedding_provider()

    if bank_rows is None:
        stmt = select(Transaction).where(
            Transaction.source == "bank",
            Transaction.status == "unmatched",
        )
        if project_id is not None:
            stmt = stmt.where(Transaction.project_id == project_id)
        bank_rows = list(db.scalars(stmt).all())
    else:
        bank_rows = [tx for tx in bank_rows if is_open_for_matching(tx)]

    if ledger_rows is None:
        stmt = select(Transaction).where(
            Transaction.source == "ledger",
            Transaction.status == "unmatched",
        )
        if project_id is not None:
            stmt = stmt.where(Transaction.project_id == project_id)
        ledger_open = list(db.scalars(stmt).all())
    else:
        ledger_open = [tx for tx in ledger_rows if is_open_for_matching(tx)]

    ledger_by_id: dict[UUID, Transaction] = {row.id: row for row in ledger_open}
    amount_index = AmountIndex.from_rows(ledger_open)

    try:
        resolved_stmt = select(func.count()).select_from(Transaction).where(
            Transaction.source == "bank",
            Transaction.status.in_(tuple(RESOLVED_STATUSES)),
        )
        if project_id is not None:
            resolved_stmt = resolved_stmt.where(Transaction.project_id == project_id)
        resolved_count = db.scalar(resolved_stmt)
        skipped = int(resolved_count or 0)
    except Exception:
        skipped = 0

    summary: dict[str, Any] = {
        "matching_run_id": str(matching_run_id),
        "processed": 0,
        "skipped_resolved": skipped,
        "exact_rule": 0,
        "semantic_match": 0,
        "llm_agent": 0,
        "decisions_written": 0,
        "notify_payloads": [],
    }

    # Tier 1 first (no embeddings), then batch-embed only leftovers + open ledger.
    after_tier1: list[Transaction] = []
    for bank_tx in bank_rows:
        if not is_open_for_matching(bank_tx):
            continue
        summary["processed"] += 1

        tier1 = amount_index.match(bank_tx)
        if tier1.matched and tier1.matched_id is not None:
            _apply_match(
                db,
                bank_tx,
                matched_id=tier1.matched_id,
                decision="matched",
                method="exact_rule",
                confidence=1.0,
                reasoning={"rule": "amount+date"},
                matching_run_id=matching_run_id,
                ledger_by_id=ledger_by_id,
            )
            amount_index.remove(tier1.matched_id)
            ledger_by_id.pop(tier1.matched_id, None)
            summary["exact_rule"] += 1
            summary["decisions_written"] += 1
            continue
        after_tier1.append(bank_tx)

    agent_leftovers: list[Transaction] = []

    if after_tier1 and not skip_semantic and provider is not None:
        # Defer flush — embeddings live on ORM objects for in-memory Tier 2.
        ensure_embeddings(
            db,
            after_tier1 + list(ledger_by_id.values()),
            provider,
            flush=False,
        )

    for bank_tx in after_tier1:
        tier2 = MatchResult(matched=False)
        if not skip_semantic:
            tier2 = try_semantic_match(
                bank_tx,
                db,
                provider=provider,
                ledger_pool=list(ledger_by_id.values()),
            )
        if tier2.matched and tier2.matched_id is not None:
            decision = apply_review_threshold(tier2.confidence, intended="matched")
            _apply_match(
                db,
                bank_tx,
                matched_id=tier2.matched_id,
                decision=decision,
                method="semantic_match",
                confidence=tier2.confidence,
                reasoning={"similarity": tier2.confidence},
                matching_run_id=matching_run_id,
                ledger_by_id=ledger_by_id,
            )
            if decision == "matched":
                amount_index.remove(tier2.matched_id)
                ledger_by_id.pop(tier2.matched_id, None)
            summary["semantic_match"] += 1
            summary["decisions_written"] += 1
            continue
        agent_leftovers.append(bank_tx)

    if agent_leftovers:
        # Rank leftovers so the limited Gemini budget hits the riskiest rows first.
        ranked = sorted(
            agent_leftovers,
            key=lambda tx: float(heuristic_score(tx, context)["risk_score"]),
            reverse=True,
        )

        async def _run_agent_pass() -> None:
            scored: list[tuple[Transaction, dict[str, Any]]] = []
            for bank_tx in ranked:
                scored.append((bank_tx, await score(bank_tx, context)))

            for bank_tx, agent_result in scored:
                row = _apply_agent_outcome(db, bank_tx, agent_result, matching_run_id)
                summary["llm_agent"] += 1
                summary["decisions_written"] += 1
                if notify and should_notify(row):
                    summary["notify_payloads"].append(build_n8n_payload(row, transaction=bank_tx))

        asyncio.run(_run_agent_pass())

    # One round-trip for all status + decision + embedding writes.
    db.flush()
    return summary
