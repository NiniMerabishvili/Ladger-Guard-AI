# Deployment guide — Ledger Guard

Plan target (implementation plan §9):

| Piece | Host |
|---|---|
| Database | **Supabase** (pgvector) — already recommended |
| Backend | **Railway** or **Render** (Docker) |
| Frontend | **Vercel** |
| Automation | **n8n Cloud** → ClickUp |

Deploy order: **DB → Backend → n8n webhook URL → Frontend**.

---

## 0. Accounts you need

1. [Supabase](https://supabase.com) — project with `vector` extension (you may already have this)
2. [Railway](https://railway.app) **or** [Render](https://render.com)
3. [Vercel](https://vercel.com)
4. [n8n Cloud](https://n8n.io) (trial/cloud) + ClickUp API token in n8n only
5. Optional: Google AI Studio key if `LLM_PROVIDER=gemini`

Push the repo to GitHub first (Vercel/Railway deploy from Git).

---

## 1. Database (Supabase) — do this first

1. Open Supabase → **Database → Extensions** → enable **`vector`**.
2. **Project Settings → Database** → copy the **Session pooler** URI (port **5432**), not Transaction pooler (6543).
3. Convert for SQLAlchemy:

```text
postgresql+psycopg://postgres.PROJECT_REF:PASSWORD@aws-…pooler.supabase.com:5432/postgres?sslmode=require
```

URL-encode special characters in the password (`:` → `%3A`, `*` → `%2A`).

4. From your machine (once), apply migrations:

```bash
cd backend
# DATABASE_URL in .env points at Supabase
python -m alembic upgrade head
```

You should see `0001_initial_schema` applied. Tables: `transactions`, `decisions`.

---

## 2. Backend (Railway — recommended)

### 2.1 Create the service

1. Railway → **New Project** → **Deploy from GitHub** → select this repo.
2. Set **Root Directory** to `backend` (where `Dockerfile` lives).
3. Railway detects the Dockerfile and builds it.

### 2.2 Environment variables

In Railway → Variables, set:

| Variable | Example / notes |
|---|---|
| `DATABASE_URL` | Same Supabase session-pooler URL as above |
| `REVIEW_CONFIDENCE_THRESHOLD` | `0.7` |
| `EMBEDDING_PROVIDER` | `local` (needs ~1–2 GB RAM) or skip heavy model until seed |
| `LLM_PROVIDER` | `gemini` or `claude` |
| `GOOGLE_API_KEY` / `ANTHROPIC_API_KEY` | Optional; agent falls back if missing/invalid |
| `N8N_WEBHOOK_URL` | Paste **after** n8n step 3 (production webhook URL) |
| `N8N_WEBHOOK_SECRET` | Same random string you put in n8n Header Auth |
| `CORS_ORIGINS` | `http://localhost:5173,https://YOUR-APP.vercel.app` |

### 2.3 Generate a public URL

Railway → Settings → **Networking** → **Generate Domain**.

You get something like:

```text
https://ledger-guard-api-production.up.railway.app
```

Smoke test:

```bash
curl https://YOUR-BACKEND.up.railway.app/health
# {"status":"ok"}
```

Open `/docs` for Swagger.

### 2.4 Render alternative

1. New **Web Service** → connect GitHub → root `backend` → Docker.
2. Same env vars as above.
3. Health check path: `/health`.

---

## 3. n8n Cloud → ClickUp

1. Keep (or import) [n8n/reconciliation-workflow.json](../n8n/reconciliation-workflow.json).
2. Activate the workflow → copy the **Production** webhook URL  
   (`https://….app.n8n.cloud/webhook/decision`).
3. Put that URL in Railway as `N8N_WEBHOOK_URL`.
4. Header Auth: `X-Webhook-Secret` = same value as `N8N_WEBHOOK_SECRET`.
5. ClickUp credential stays **only** in n8n.
6. Test:

```bash
curl -X POST https://YOUR-BACKEND/webhook/decision \
  -H "Content-Type: application/json" \
  -H "X-Webhook-Secret: YOUR_SECRET" \
  -d "{\"transaction_id\":\"demo-1\",\"decision\":\"pending_review\",\"confidence\":0.65,\"risk_score\":0.65,\"risk_factors\":[\"unknown_counterparty\"],\"reasoning\":\"deploy test\",\"method\":\"llm_agent\"}"
```

Confirm a ClickUp task appears.

---

## 4. Frontend (Vercel)

### 4.1 Import project

1. Vercel → **Add New Project** → import the GitHub repo.
2. **Root Directory:** `frontend`
3. Framework: Vite (auto).
4. Build: `npm run build` · Output: `dist`

### 4.2 Environment

| Variable | Value |
|---|---|
| `VITE_API_URL` | `https://YOUR-BACKEND.up.railway.app` **(no trailing slash)** |

Redeploy after setting env (Vite bakes this in at build time).

### 4.3 CORS

Update Railway `CORS_ORIGINS` to include:

```text
https://YOUR-APP.vercel.app
```

Redeploy backend (or restart) so CORS picks it up.

### 4.4 SPA routes

`frontend/vercel.json` already rewrites all paths to `index.html` so `/review` and `/transactions/:id` work on refresh.

### 4.6 Stale UI after redeploy

GitHub can be current while the browser still shows an old Vercel build. Check:

1. **Root Directory** is `frontend` (Settings → General).
2. **Production Branch** is `main`.
3. Deployments → open the latest **Production** deployment (not an old Preview URL) and confirm the commit SHA matches GitHub.
4. Hard refresh (`Ctrl+Shift+R`) or open the site in a private window.
5. Sidebar shows `build <sha>` — it must match the short SHA of the commit you expect.
6. Env `VITE_API_URL` must be your Railway backend URL (no trailing slash), then **Redeploy** (Vite bakes env in at build time).

`vercel.json` sets `Cache-Control: no-cache` on `index.html` so the CDN does not keep an old entry HTML that points at outdated JS.

---

## 5. First production data run

With the backend public URL:

```bash
# If CSVs are in the container image under data/ — or upload via your own script
curl -X POST https://YOUR-BACKEND/ingest
curl -X POST https://YOUR-BACKEND/reconcile/run
curl -s https://YOUR-BACKEND/metrics
```

Then open the Vercel Review queue and Approve one item.

> Note: default `backend/data/*.csv` may be header-only until you generate/seed rows. Seed via SQL or a small script if ingest returns `total: 0`.

---

## 6. Post-deploy checklist

- [ ] `GET /health` → `ok`
- [ ] Vercel UI loads without CORS errors
- [ ] `POST /ingest` + `POST /reconcile/run` succeed
- [ ] Dashboard shows method breakdown / spend
- [ ] Review Approve writes `human_override` and updates audit trail
- [ ] n8n → ClickUp task for `pending_review`
- [ ] Paste public URLs + GIF into the root README **Demo** section

---

## 7. Common failures

| Symptom | Fix |
|---|---|
| CORS blocked | Add exact Vercel origin to `CORS_ORIGINS` (https, no trailing slash) |
| DB auth failed | Session pooler 5432 + URL-encoded password |
| `vector` type missing | Enable extension in Supabase dashboard, re-run alembic |
| Frontend calls localhost | `VITE_API_URL` missing → rebuild on Vercel |
| OOM on Railway | Bump memory, or keep Tier 2 off until you have RAM (`local` model is heavy) |
| ClickUp empty | Check n8n execution log; body often under `$json.body.*` on Cloud |
| `Can't locate revision identified by '0002_projects'` | Your **Supabase DB is already migrated**. The failing logs are usually an **old Railway deployment crash-looping** (same deployment id), not a fresh build. Fix: (1) Railway service **Root Directory = `backend`**, (2) remove any custom start command that only runs `alembic upgrade head`, or set it to `python -m app.db.migrate && uvicorn app.main:app --host 0.0.0.0 --port $PORT`, (3) **Deploy → Redeploy** from latest `main` with clear build cache. Immediate unblock: set start command to `uvicorn app.main:app --host 0.0.0.0 --port $PORT` (skip alembic — schema is already applied). |

---

## Suggested order this afternoon

1. Confirm Supabase `vector` + alembic head  
2. Deploy Railway backend + `/health`  
3. Point `N8N_WEBHOOK_URL` at Cloud webhook  
4. Deploy Vercel with `VITE_API_URL`  
5. Fix `CORS_ORIGINS`  
6. Ingest / reconcile / demo GIF  
