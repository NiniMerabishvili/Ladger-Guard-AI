FROM python:3.12-slim

WORKDIR /app

COPY pyproject.toml alembic.ini ./
COPY app ./app

# Fail the build early if project migrations are missing from the image context.
RUN test -f app/db/migrations/versions/0001_initial_schema.py \
    && test -f app/db/migrations/versions/0002_projects.py

RUN pip install --no-cache-dir . \
    && python -c "from alembic.config import Config; from alembic.script import ScriptDirectory; \
s=ScriptDirectory.from_config(Config('alembic.ini')); \
assert '0002_projects' in s.get_heads(), s.get_heads()"

EXPOSE 8000

# Railway/Render set $PORT; default 8000 for local Docker.
CMD ["sh", "-c", "python -m app.db.migrate && uvicorn app.main:app --host 0.0.0.0 --port ${PORT:-8000}"]
