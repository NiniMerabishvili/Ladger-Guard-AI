-- Enable pgvector on first container start (implementation plan §2.1).
-- Tables are created by Alembic (see app/db/migrations/versions/).
CREATE EXTENSION IF NOT EXISTS vector;
