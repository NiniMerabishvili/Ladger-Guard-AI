# AI Reconciliation & Anomaly Triage Copilot

Back-office teams still match bank statements against the internal ledger by hand. This copilot auto-matches the majority of transactions, sends only ambiguous or suspicious cases to review, and records an audit trail for every decision.

## Architecture

FastAPI owns matching, scoring, and routing. n8n only forwards flagged / pending-review decisions to Airtable and Slack. PostgreSQL + pgvector stores transactions, decisions, and embeddings.

Details: [docs/architecture.md](docs/architecture.md).

## Metrics

See [docs/metrics-report.md](docs/metrics-report.md) (filled after the first synthetic run).

## Integration Layer

n8n workflow export: [n8n/reconciliation-workflow.json](n8n/reconciliation-workflow.json). Flagged / pending-review rows create a **ClickUp** task (screenshot: [n8n/screenshot.png](n8n/screenshot.png)).

## AI providers (Claude vs Gemini)

Both implement `ModelProvider.generate_structured(prompt, schema)`. Switch with `LLM_PROVIDER` in `.env`. If the API fails after retries, the agent returns a low-confidence fallback and does **not** stop the pipeline.

Mock cost per call (dashboard): Claude $0.003, Gemini $0.0002, local embeddings $0.

Live comparison (same leftover cases; one key is enough — Gemini-only is fine):

```bash
cd backend
python -m scripts.compare_providers
```

| Case | Claude risk | Gemini risk | Notes |
|---|---|---|---|
| TBD | — | — | Fill after a live run. Gemini-only is fine until an Anthropic key is available. |

## Limitations

- Synthetic data is not production data — performance may differ on a real dataset.
- The anomaly agent's false positive rate is not production-tuned; this is a portfolio demo, not a compliance system.
- Currency conversion uses a fixed-rate mock, not a real-time FX API.

## How to run locally

```bash
cp backend/.env.example backend/.env
docker compose up --build
```

The backend container runs `alembic upgrade head` on startup (pgvector extension, enums, `transactions`, `decisions`).

- API: http://localhost:8000
- Frontend (after `cd frontend && npm install && npm run dev`): http://localhost:5173
- n8n: http://localhost:5678

To apply migrations against a running database without Docker (local Postgres or Supabase):

```bash
cd backend
pip install -e ".[dev]"
alembic upgrade head
```

Use the **Direct** or **Session pooler** connection string (port 5432), not the Transaction pooler (6543). Enable the `vector` extension in the Supabase dashboard first (Database → Extensions).

## Demo

Demo GIF/link will be added after deployment.
