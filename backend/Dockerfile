FROM python:3.12-slim

WORKDIR /app

COPY pyproject.toml alembic.ini ./
COPY app ./app

RUN test -f app/db/migrations/versions/0001_initial_schema.py \
    && test -f app/db/migrations/versions/0002_projects.py \
    && test -f app/run.py

RUN pip install --no-cache-dir .

EXPOSE 8000

CMD ["python", "-m", "app.run"]
