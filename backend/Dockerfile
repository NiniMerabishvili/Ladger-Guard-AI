FROM python:3.12-slim

WORKDIR /app

COPY pyproject.toml alembic.ini ./
COPY app ./app

RUN pip install --no-cache-dir .

EXPOSE 8000

# Railway/Render set $PORT; default 8000 for local Docker.
CMD ["sh", "-c", "alembic upgrade head && uvicorn app.main:app --host 0.0.0.0 --port ${PORT:-8000}"]
