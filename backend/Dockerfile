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

# Python reads PORT from env — works even when Railway does not expand $PORT in CMD.
CMD ["python", "-m", "app.run"]
