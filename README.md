# Ledger Guard AI

Portfolio MVP for FinTech back-office ops: match a **bank statement** CSV to an **internal ledger**, score leftovers with an LLM, and send only ambiguous cases to a human — with a full audit trail on every decision.

> Target on synthetic data: **≥70% auto-matched**, confidence **&lt; 0.7 never auto-resolved**, every decision append-only.

---

## Problem

Operations teams reconcile the bank feed against the books by hand — scanning lines like `$5,000 UNKNOWN VENDOR WIRE` against dozens of ledger rows, hunting duplicates, off-by-one dates, and FX noise. The work is slow, easy to miss, and does not scale.

**Ledger Guard** automates the obvious matches, keeps explainability on every step, and routes only low-confidence or risky leftovers into a review queue (and optionally ClickUp via n8n).

---

## What you can do

| Feature | Description |
|---|---|
| **Projects** | Create, open, and delete workspaces. Each upload run lives in its own project so older summaries stay available. |
| **Upload & run** | Upload bank + ledger CSVs (≤5 MB each), ingest, reconcile, and see match stats + pending review cards on the same page. |
| **Three-tier matching** | Exact rules → local semantic embeddings → LLM anomaly agent for leftovers. |
| **Review queue** | Approve / reject / manual-match with append-only decision history. |
| **Dashboard** | Auto-match %, pending/flagged counts, method breakdown, estimated AI spend & labor savings (scoped to the active project). |
| **ClickUp via n8n** | Flagged / pending_review decisions create ClickUp tasks after reconcile commits. |

---

## Architecture

All matching, scoring, and routing live in **FastAPI**. **n8n** is glue only (webhook → ClickUp). **PostgreSQL + pgvector** stores transactions, decisions, embeddings, and projects.

```
┌─────────────────┐      ┌──────────────────────────────────────────┐
│  React / Vite   │      │              FastAPI Backend               │
│  Projects ·     │◄────►│                                            │
│  Upload · Dash  │ REST │  Ingest → Tier 1 → Tier 2 → Anomaly Agent │
│  · Review       │      │              ↓                             │
└─────────────────┘      │         Decisions + Audit                  │
                         └──────────────────┬─────────────────────────┘
                                            │ webhook (after commit)
                                   ┌────────▼────────┐
                                   │  n8n → ClickUp  │
                                   └─────────────────┘
                         ┌──────────────────┐
                         │ PostgreSQL +     │
                         │ pgvector         │
                         └──────────────────┘
```

| Stage | What it does | Cost |
|---|---|---|
| **Tier 1 — Exact rules** | Amount ±$0.01 and date ±1 day (amount index built once per run) | Free |
| **Tier 2 — Semantic** | Batch local embeddings (`all-MiniLM-L6-v2`, 384-dim) + in-memory cosine over open ledger rows; amount ±3%, date ±3 days, similarity &gt; 0.85 | Local ≈ $0 |
| **Anomaly agent** | Structured JSON risk score for leftovers (Gemini or Claude via `ModelProvider`); live LLM calls capped by `LLM_MAX_PER_RUN` | Paid API only when needed |
| **Human-in-the-loop** | Confidence &lt; 0.7 → `pending_review`; Approve / Reject / Manual match | Human |

Details: [docs/architecture.md](docs/architecture.md).

### Stack

| Layer | Choice |
|---|---|
| API | FastAPI, SQLAlchemy 2, Alembic, Pydantic |
| DB | PostgreSQL 16 + pgvector (Docker or Supabase) |
| Frontend | React 18, TypeScript, Vite, TanStack Query, Tailwind CSS v4, Recharts |
| Automation | n8n → ClickUp task |
| Embeddings | Local MiniLM by default (`EMBEDDING_PROVIDER=local`) |
| LLM | Gemini or Claude (`LLM_PROVIDER=gemini` \| `claude`) |

### Performance notes

Recent reconcile/ingest optimizations:

- Tier 1 amount buckets built **once** and updated on match
- Tier 2 similarity scored **in memory** over project ledger vectors (no per-row pgvector round-trip)
- Decisions / status / embeddings **batched** into a single DB flush per run
- CSV ingest uses bulk `INSERT` + fast frame → records conversion
- Embeddings batch-encoded (`batch_size=64`); model warmed at API startup
- n8n webhooks fire in **background** after commit

---

## Metrics

Dashboard: **GET `/metrics?project_id=`** → auto-match %, pending review %, flagged %, method breakdown, running AI spend, assumption-based labor savings.

| Metric | Target / note |
|---|---|
| Auto-matched % | ≥ **70%** on the synthetic dataset |
| Tier 2 share | Roughly **10–20%** of rows should reach embeddings (rules filter the rest) |
| False positive rate | **Not production-tuned** — measured for transparency, not claimed as zero |
| Cost per reconciliation | Mock rates on the dashboard: Claude **$0.003**/call, Gemini **$0.0002**/call, local embeddings **$0** |
| Labor savings | Assumption: **$2.50** per auto-match (labeled on the UI, not a measured production figure) |
| Idempotency | Re-running `POST /reconcile/run` does **not** duplicate `decisions` rows |

Live numbers after a seed + reconcile run: open the Dashboard or see [docs/metrics-report.md](docs/metrics-report.md).

```bash
curl -s "http://localhost:8000/metrics?project_id=<PROJECT_ID>"
```

---

## Integration layer (n8n → ClickUp)

When a decision is `flagged` or `pending_review`, the backend POSTs to the n8n webhook **after** the reconcile commit. n8n creates a **ClickUp** task in the review list (high risk → urgent priority).

| Artifact | Link |
|---|---|
| Workflow export | [n8n/reconciliation-workflow.json](n8n/reconciliation-workflow.json) |
| Screenshot | Drop a capture at `n8n/screenshot.png` after a live ClickUp run |

**Payload (simplified):** `task_name`, `description`, `transaction_id`, `decision`, `confidence`, `risk_score`, `risk_factors`, `reasoning`, `method`, `high_priority`.

In the ClickUp node, set **Name** to `{{$json.body.task_name}}` (and description similarly) so task titles match the review-queue wording.

Protect the webhook with `N8N_WEBHOOK_SECRET` (`X-Webhook-Secret`). Put the **ClickUp API token only in n8n credentials**, not in `backend/.env`.

---

## Limitations

Quoted from the tech spec (section 10):

- Synthetic data ≠ production data — performance may differ on a real dataset
- The anomaly agent's false positive rate is not tuned to production level — this is a portfolio demo, not a production compliance system
- Currency conversion — mock/fixed rate, not real-time

Also intentional for the MVP:

- Explainability beats overconfident flags: invalid LLM JSON → low-confidence fallback (`risk_score = 0.1`), never a high-risk auto-flag
- No paid Anthropic/OpenAI keys required for the demo path (`EMBEDDING_PROVIDER=local`; LLM can be mocked in tests)
- No multi-user auth yet — projects are shared workspace state

---

## How to run locally

### Prerequisites

- Docker (Postgres + optional n8n), or a Supabase project with the `vector` extension
- Python 3.11+
- Node 20+ (frontend)

### 1. Environment

```bash
cp backend/.env.example backend/.env
```

Set at least:

| Variable | Purpose |
|---|---|
| `DATABASE_URL` | Local Docker or Supabase **session/direct** pooler (port **5432**, not 6543) |
| `EMBEDDING_PROVIDER` | `local` (default) or `openai` |
| `LLM_PROVIDER` | `gemini` or `claude` |
| `LLM_MAX_PER_RUN` | Cap live LLM calls per reconcile (default `2`; rest use heuristics) |
| `GOOGLE_API_KEY` / `ANTHROPIC_API_KEY` | Provider key for the chosen LLM |
| `N8N_WEBHOOK_URL` / `N8N_WEBHOOK_SECRET` | Optional until you wire ClickUp |
| `CORS_ORIGINS` | Defaults include `http://localhost:5173` |
| `REVIEW_CONFIDENCE_THRESHOLD` | Default `0.7` |

### 2. Database + API

**Option A — Docker Compose**

```bash
docker compose up --build
```

- API: http://localhost:8000
- n8n: http://localhost:5678
- Postgres: `localhost:5432`

**Option B — Local API + Docker DB or Supabase**

```bash
cd backend
pip install -e ".[dev]"
python -m alembic upgrade head
python -m uvicorn app.main:app --reload --port 8000
```

### 3. Frontend

```bash
cd frontend
npm install
npm run dev
```

UI: http://localhost:5173

| Page | Route |
|---|---|
| Projects | `/projects` |
| Upload & run | `/upload` |
| Dashboard | `/` |
| Review queue | `/review` |

### 4. Typical flow

1. Open **Projects** → **Create project** (or use **Upload new project**).
2. On **Upload & run**, pick bank + ledger CSVs → upload & reconcile.
3. Inspect match stats and pending cards on the upload page, or open **Dashboard** / **Review**.
4. Delete a project from the projects list when you no longer need it (removes its transactions and decisions).

Script / curl equivalent:

```bash
# Create a project
curl -s -X POST http://localhost:8000/projects \
  -H "Content-Type: application/json" \
  -d "{\"name\":\"March close\"}"

# Upload CSVs into that project (multipart), then reconcile
curl -X POST http://localhost:8000/ingest \
  -F "bank_file=@backend/data/bank_statement.csv" \
  -F "ledger_file=@backend/data/internal_ledger.csv" \
  -F "project_id=<PROJECT_ID>"

curl -X POST "http://localhost:8000/reconcile/run?project_id=<PROJECT_ID>"

# Review
curl -X POST http://localhost:8000/review/<tx_id> \
  -H "Content-Type: application/json" \
  -d "{\"decision\":\"approve\",\"reviewed_by\":\"reviewer\"}"
```

### 5. Tests

```bash
cd backend
python -m pytest tests/ -q
```

LLM and embedding calls are mocked in tests — no live API keys required.

### 6. Optional: compare Claude vs Gemini

```bash
cd backend
python -m scripts.compare_providers
```

---

## Demo

| Item | Status |
|---|---|
| Local demo | Projects + Upload + Dashboard + Review at http://localhost:5173 with API on :8000 |
| Deployed URL | *Add after Railway/Render + Vercel deploy* — see [docs/DEPLOY.md](docs/DEPLOY.md) |
| Demo GIF (30–60s) | *Add for LinkedIn after a recorded run* |

**Suggested GIF path:** create project → upload CSVs → auto-match % on Upload/Dashboard → open Review → Approve a low-confidence wire → audit trail updates → ClickUp task appears.

---

## API surface

```
GET    /health
GET    /projects
POST   /projects
GET    /projects/{project_id}
DELETE /projects/{project_id}

POST   /ingest                      # multipart: bank_file, ledger_file, project_id
POST   /reconcile/run?project_id=

GET    /transactions?status=&source=&date_from=&date_to=&project_id=
GET    /transactions/{id}
GET    /decisions/{tx_id}
POST   /review/{tx_id}              # approve | reject | manual_match
GET    /metrics?project_id=

POST   /webhook/decision
```

---

## Repository layout

```
Ledger_Guard_AI/
├── backend/          # FastAPI app, Alembic migrations, tests, sample CSVs
├── frontend/         # React / Vite UI
├── n8n/              # ClickUp workflow export
├── docs/             # architecture, deploy, metrics report
├── docker-compose.yml
├── README.md
├── AI_Reconciliation_Copilot_TechSpec_EN.md
└── AI_Reconciliation_Copilot_Implementation_Plan_EN.md
```

---

## Project docs

- [Technical specification](AI_Reconciliation_Copilot_TechSpec_EN.md)
- [Implementation plan](AI_Reconciliation_Copilot_Implementation_Plan_EN.md)
- [Architecture notes](docs/architecture.md)
- [Metrics report](docs/metrics-report.md)
- [Deploy notes](docs/DEPLOY.md)
