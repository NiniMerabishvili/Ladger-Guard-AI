"""Add projects table and project_id on transactions.

Revision ID: 0002_projects
Revises: 0001_initial_schema
Create Date: 2026-09-06
"""

from collections.abc import Sequence

from alembic import op

revision: str = "0002_projects"
down_revision: str | None = "0001_initial_schema"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    # Idempotent so re-deploys / stamp repairs never fail if schema already exists.
    op.execute(
        """
        CREATE TABLE IF NOT EXISTS projects (
            id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
            name VARCHAR(200) NOT NULL,
            status VARCHAR(20) NOT NULL DEFAULT 'open',
            bank_filename TEXT,
            ledger_filename TEXT,
            summary JSONB,
            created_at TIMESTAMP DEFAULT now(),
            updated_at TIMESTAMP DEFAULT now()
        );
        """
    )
    op.execute("CREATE INDEX IF NOT EXISTS idx_projects_created ON projects(created_at DESC);")

    op.execute(
        """
        INSERT INTO projects (id, name, status, summary)
        SELECT gen_random_uuid(), 'Legacy workspace', 'completed', NULL
        WHERE EXISTS (SELECT 1 FROM transactions LIMIT 1)
          AND NOT EXISTS (SELECT 1 FROM projects LIMIT 1);
        """
    )

    op.execute(
        """
        ALTER TABLE transactions
        ADD COLUMN IF NOT EXISTS project_id UUID REFERENCES projects(id);
        """
    )
    op.execute(
        """
        UPDATE transactions
        SET project_id = (SELECT id FROM projects ORDER BY created_at ASC LIMIT 1)
        WHERE project_id IS NULL
          AND EXISTS (SELECT 1 FROM projects LIMIT 1);
        """
    )
    op.execute("CREATE INDEX IF NOT EXISTS idx_transactions_project ON transactions(project_id);")


def downgrade() -> None:
    op.execute("DROP INDEX IF EXISTS idx_transactions_project;")
    op.execute("ALTER TABLE transactions DROP COLUMN IF EXISTS project_id;")
    op.execute("DROP INDEX IF EXISTS idx_projects_created;")
    op.execute("DROP TABLE IF EXISTS projects;")
