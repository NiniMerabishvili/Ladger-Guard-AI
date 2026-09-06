# Ledger Guard — AI Reconciliation & Anomaly Triage Copilot

Portfolio MVP for FinTech back-office ops: match a **bank statement** to an **internal ledger**, score leftovers with an LLM, and send only ambiguous cases to a human — with a full audit trail on every decision.

> Target on synthetic data: **≥70% auto-matched**, confidence **&lt; 0.7 never auto-resolved**, every decision append-only.

---

## 1. Problem

Every day, operations teams reconcile the bank feed against the books by hand.

That means staring at lines like `$5,000 UNKNOWN VENDOR WIRE` next to dozens of ledger rows, hunting duplicates, off-by-one dates, and FX noise. The work is slow, easy to miss, and does not scale.

**Ledger Guard** automates the obvious matches, keeps explainability on every step, and routes only low-confidence or risky leftovers into a review queue (and optionally ClickUp via n8n).

---

## 2. Architecture

All matching, scoring, and routing live in **FastAPI**. **n8n** is glue only (webhook → ClickUp). **PostgreSQL + pgvector** stores transactions, decisions, and embeddings.

```
┌─────────────────┐      ┌──────────────────────────────────────────┐
│  React / Vite   │      │              FastAPI Backend               │
│  Dashboard +    │◄────►│                                            │
│  Review Queue   │ REST │  Ingest → Tier 1 → Tier 2 → Anomaly Agent │
└─────────────────┘      │              ↓                             │
                         │         Decisions + Audit                  │
                         └──────────────────┬─────────────────────────┘
                                            │ webhook
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
| **Tier 1 — Exact rules** | Amount ±$0.01 and date ±1 day | Free |
| **Tier 2 — Semantic** | Local embeddings (`all-MiniLM-L6-v2`, 384-dim) + pgvector cosine search; amount ±3%, date ±3 days, similarity &gt; 0.85 | Local ≈ $0 |
| **Anomaly agent** | Structured JSON risk score for leftovers (Claude or Gemini via `ModelProvider`) | Paid API only when needed |
| **Human-in-the-loop** | Confidence &lt; 0.7 → `pending_review`; Approve / Reject / Manual match | Human |

Details: [docs/architecture.md](docs/architecture.md).

### Stack

| Layer | Choice |
|---|---|
| API | FastAPI, SQLAlchemy, Alembic, Pydantic |
| DB | PostgreSQL 16 + pgvector (Docker or Supabase) |
| Frontend | React, TypeScript, Vite, TanStack Query, Tailwind CSS v4, Recharts |
| Automation | n8n → ClickUp task |
| LLM | Claude and/or Gemini (swappable); embeddings default **local** |

---

## 3. Metrics

Dashboard: **GET `/metrics`** → auto-match %, pending review %, flagged %, method breakdown, running AI spend, assumption-based labor savings.

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
curl -s http://localhost:8000/metrics
```

---

## 4. Integration Layer

When a decision is `flagged` or `pending_review`, the backend POSTs to the n8n webhook. n8n creates a **ClickUp** task in the review list (high risk → urgent priority).

| Artifact | Link |
|---|---|
| Workflow export | [n8n/reconciliation-workflow.json](n8n/reconciliation-workflow.json) |
| Screenshot | Drop a capture at `n8n/screenshot.png` after a live ClickUp run |

**Payload (simplified):** `transaction_id`, `decision`, `confidence`, `risk_score`, `risk_factors`, `reasoning`, `method`, `high_priority`.

Protect the webhook with `N8N_WEBHOOK_SECRET` (`X-Webhook-Secret`). Put the **ClickUp API token only in n8n credentials**, not in `backend/.env`.

---

## 5. Limitations

Quoted from the tech spec (section 10):

- Synthetic data ≠ production data — performance may differ on a real dataset
- The anomaly agent's false positive rate is not tuned to production level — this is a portfolio demo, not a production compliance system
- Currency conversion — mock/fixed rate, not real-time

Also intentional for the MVP:

- Explainability beats overconfident flags: invalid LLM JSON → low-confidence fallback (`risk_score = 0.1`), never a high-risk auto-flag
- No paid Anthropic/OpenAI keys required for the demo path (`EMBEDDING_PROVIDER=local`; LLM can be mocked in tests)

---

## 6. How to run locally

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
| `LLM_PROVIDER` | `claude` or `gemini` |
| `N8N_WEBHOOK_URL` / `N8N_WEBHOOK_SECRET` | Optional until you wire ClickUp |

### 2. Database + API

**Option A — Docker Compose**

```bash
docker compose up --build
```

- API: http://localhost:8000  
- n8n: http://localhost:5678  
- Postgres: `localhost:5432`

**Option B — Local API + Supabase**

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

UI: http://localhost:5173 — **Dashboard**, **Review queue**, **Transaction detail** (audit trail).

### 4. Seed → reconcile → review

```bash
# With CSV rows in backend/data/
curl -X POST http://localhost:8000/ingest
curl -X POST http://localhost:8000/reconcile/run

# Review UI, or:
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

## 7. Demo

| Item | Status |
|---|---|
| Local demo | Dashboard + Review queue at http://localhost:5173 with API on :8000 |
| Deployed URL | *Add after Railway/Render + Vercel deploy* |
| Demo GIF (30–60s) | *Add for LinkedIn after a recorded run* |

**Suggested GIF path:** ingest → auto-match % on Dashboard → open Review queue → Approve a low-confidence wire → audit trail updates → ClickUp task appears.

---

## API surface

```
POST /ingest
POST /reconcile/run
GET  /transactions?status=pending_review
GET  /transactions/{id}
GET  /decisions/{tx_id}
POST /review/{tx_id}
GET  /metrics
POST /webhook/decision
GET  /health
```

---

## Project docs

- [Technical specification](AI_Reconciliation_Copilot_TechSpec_EN.md)
- [Implementation plan](AI_Reconciliation_Copilot_Implementation_Plan_EN.md)
- [Architecture notes](docs/architecture.md)
- [Metrics report](docs/metrics-report.md)
