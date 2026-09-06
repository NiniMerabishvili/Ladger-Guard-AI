"""Initial schema: pgvector, enums, transactions, decisions.

Revision ID: 0001_initial_schema
Revises:
Create Date: 2026-09-04
"""

from collections.abc import Sequence

from alembic import op

revision: str = "0001_initial_schema"
down_revision: str | None = None
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.execute("CREATE EXTENSION IF NOT EXISTS vector;")

    op.execute("CREATE TYPE source_enum AS ENUM ('bank', 'ledger');")
    op.execute("CREATE TYPE decision_enum AS ENUM ('matched', 'flagged', 'pending_review');")
    op.execute(
        "CREATE TYPE method_enum AS ENUM "
        "('exact_rule', 'semantic_match', 'llm_agent', 'human_override');"
    )

    op.execute(
        """
        CREATE TABLE transactions (
            id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
            source source_enum NOT NULL,
            date DATE NOT NULL,
            amount NUMERIC(14,2) NOT NULL,
            currency VARCHAR(3) NOT NULL,
            description TEXT NOT NULL,
            counterparty TEXT,
            embedding VECTOR(384),
            status VARCHAR(20) DEFAULT 'unmatched',
            created_at TIMESTAMP DEFAULT now()
        );
        """
    )

    op.execute(
        """
        CREATE TABLE decisions (
            id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
            transaction_id UUID REFERENCES transactions(id),
            matched_transaction_id UUID REFERENCES transactions(id) NULL,
            decision decision_enum NOT NULL,
            method method_enum NOT NULL,
            confidence FLOAT NOT NULL,
            reasoning JSONB,
            model_used VARCHAR(50),
            reviewed_by VARCHAR(100),
            matching_run_id UUID,
            created_at TIMESTAMP DEFAULT now()
        );
        """
    )

    op.execute(
        """
        CREATE INDEX idx_transactions_embedding ON transactions
            USING ivfflat (embedding vector_cosine_ops) WITH (lists = 100);
        """
    )
    op.execute("CREATE INDEX idx_decisions_tx ON decisions(transaction_id);")


def downgrade() -> None:
    op.execute("DROP INDEX IF EXISTS idx_decisions_tx;")
    op.execute("DROP INDEX IF EXISTS idx_transactions_embedding;")
    op.execute("DROP TABLE IF EXISTS decisions;")
    op.execute("DROP TABLE IF EXISTS transactions;")
    op.execute("DROP TYPE IF EXISTS method_enum;")
    op.execute("DROP TYPE IF EXISTS decision_enum;")
    op.execute("DROP TYPE IF EXISTS source_enum;")
