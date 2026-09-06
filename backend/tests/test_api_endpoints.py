"""API endpoint happy-path tests."""

from datetime import date, datetime
from decimal import Decimal
from unittest.mock import MagicMock, patch
from uuid import uuid4

from fastapi.testclient import TestClient

from app.db.models import Decision, Transaction
from app.db.session import get_db
from app.main import app


def test_get_decisions_returns_chronological_audit_trail() -> None:
    tx_id = uuid4()
    rows = [
        Decision(
            id=uuid4(),
            transaction_id=tx_id,
            decision="matched",
            method="exact_rule",
            confidence=1.0,
            reasoning={"rule": "amount+date"},
            created_at=datetime(2026, 9, 1, 10, 0, 0),
        ),
        Decision(
            id=uuid4(),
            transaction_id=tx_id,
            decision="flagged",
            method="llm_agent",
            confidence=0.82,
            reasoning={"explanation": "unknown vendor"},
            model_used="claude-sonnet-4-6",
            created_at=datetime(2026, 9, 1, 10, 5, 0),
        ),
    ]
    db = MagicMock()
    db.scalars.return_value.all.return_value = rows

    def _override() -> MagicMock:
        yield db

    app.dependency_overrides[get_db] = _override
    try:
        client = TestClient(app)
        response = client.get(f"/decisions/{tx_id}")
    finally:
        app.dependency_overrides.clear()

    assert response.status_code == 200
    payload = response.json()
    assert len(payload) == 2
    assert payload[0]["method"] == "exact_rule"
    assert payload[1]["method"] == "llm_agent"
    assert payload[0]["created_at"] < payload[1]["created_at"]


def test_list_transactions_includes_latest_decision() -> None:
    tx_id = uuid4()
    tx = Transaction(
        id=tx_id,
        source="bank",
        date=date(2026, 9, 1),
        amount=Decimal("5000.00"),
        currency="USD",
        description="UNKNOWN VENDOR WIRE",
        counterparty="ACME LLC",
        status="pending_review",
    )
    older = Decision(
        id=uuid4(),
        transaction_id=tx_id,
        decision="pending_review",
        method="llm_agent",
        confidence=0.4,
        reasoning={"explanation": "older"},
        created_at=datetime(2026, 9, 1, 9, 0, 0),
    )
    newest = Decision(
        id=uuid4(),
        transaction_id=tx_id,
        decision="pending_review",
        method="llm_agent",
        confidence=0.62,
        reasoning={
            "explanation": "New vendor wire for an unusually large amount.",
            "risk_factors": ["unknown_counterparty", "unusual_amount"],
        },
        created_at=datetime(2026, 9, 1, 10, 0, 0),
    )
    db = MagicMock()
    db.scalars.side_effect = [
        MagicMock(all=lambda: [tx]),
        MagicMock(all=lambda: [newest, older]),
    ]

    def _override() -> MagicMock:
        yield db

    app.dependency_overrides[get_db] = _override
    try:
        client = TestClient(app)
        response = client.get("/transactions?status=pending_review")
    finally:
        app.dependency_overrides.clear()

    assert response.status_code == 200
    payload = response.json()
    assert len(payload) == 1
    assert payload[0]["id"] == str(tx_id)
    assert payload[0]["status"] == "pending_review"
    assert payload[0]["latest_decision"]["confidence"] == 0.62
    assert payload[0]["latest_decision"]["reasoning"]["risk_factors"] == [
        "unknown_counterparty",
        "unusual_amount",
    ]


def test_get_transaction_404() -> None:
    db = MagicMock()
    db.get.return_value = None

    def _override() -> MagicMock:
        yield db

    app.dependency_overrides[get_db] = _override
    try:
        client = TestClient(app)
        response = client.get(f"/transactions/{uuid4()}")
    finally:
        app.dependency_overrides.clear()

    assert response.status_code == 404


def test_review_approve_writes_human_override() -> None:
    tx_id = uuid4()
    tx = Transaction(
        id=tx_id,
        source="bank",
        date=date(2026, 9, 1),
        amount=Decimal("4.50"),
        currency="USD",
        description="STARBUCKS",
        status="pending_review",
    )
    db = MagicMock()
    db.get.return_value = tx

    def _override() -> MagicMock:
        yield db

    app.dependency_overrides[get_db] = _override
    try:
        client = TestClient(app)
        response = client.post(
            f"/review/{tx_id}",
            json={"decision": "approve", "reviewed_by": "alice"},
        )
    finally:
        app.dependency_overrides.clear()

    assert response.status_code == 200
    payload = response.json()
    assert payload["method"] == "human_override"
    assert payload["decision"] == "matched"
    assert payload["reviewed_by"] == "alice"
    assert tx.status == "matched"
    db.commit.assert_called_once()


def test_ingest_endpoint_persists_normalized_rows() -> None:
    db = MagicMock()

    def _override() -> MagicMock:
        yield db

    app.dependency_overrides[get_db] = _override
    try:
        client = TestClient(app)
        with patch(
            "app.routes.ingest.ingest_files",
            return_value={"bank_count": 2, "ledger_count": 2, "total": 4},
        ) as mocked:
            response = client.post("/ingest")
    finally:
        app.dependency_overrides.clear()

    assert response.status_code == 200
    assert response.json() == {"bank_count": 2, "ledger_count": 2, "total": 4}
    mocked.assert_called_once()
    db.commit.assert_called_once()


def test_ingest_endpoint_accepts_multipart_csvs() -> None:
    db = MagicMock()

    def _override() -> MagicMock:
        yield db

    header = "transaction_id,date,amount,currency,description,counterparty\n"
    bank = (header + "b1,2026-09-01,10.00,USD,COFFEE,CAFE\n").encode()
    ledger = (header + "l1,2026-09-01,10.00,USD,Coffee POS,CAFE\n").encode()

    app.dependency_overrides[get_db] = _override
    try:
        client = TestClient(app)
        response = client.post(
            "/ingest",
            files={
                "bank_file": ("bank.csv", bank, "text/csv"),
                "ledger_file": ("ledger.csv", ledger, "text/csv"),
            },
        )
    finally:
        app.dependency_overrides.clear()

    assert response.status_code == 200
    assert response.json()["total"] == 2
    db.commit.assert_called_once()


def test_reconcile_run_endpoint_returns_summary() -> None:
    db = MagicMock()
    run_id = uuid4()

    def _override() -> MagicMock:
        yield db

    summary = {
        "matching_run_id": str(run_id),
        "processed": 3,
        "skipped_resolved": 0,
        "exact_rule": 2,
        "semantic_match": 0,
        "llm_agent": 1,
        "decisions_written": 3,
    }
    app.dependency_overrides[get_db] = _override
    try:
        client = TestClient(app)
        with patch("app.routes.reconcile.run_reconciliation", return_value=summary) as mocked:
            response = client.post(f"/reconcile/run?run_id={run_id}")
    finally:
        app.dependency_overrides.clear()

    assert response.status_code == 200
    payload = response.json()
    assert payload["exact_rule"] == 2
    assert payload["llm_agent"] == 1
    assert payload["decisions_written"] == 3
    mocked.assert_called_once()
    db.commit.assert_called_once()
