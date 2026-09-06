# Technical Specification: AI Reconciliation & Anomaly Triage Copilot

**Client:** FinTech Back-Office Operations (hypothetical, for portfolio project)
**Role:** AI Engineer (solo)
**Version:** v1.0
**Estimated duration:** 2 weeks (MVP)

---

## 1. Context and Problem

A back-office team manually compares the bank statement (bank feed) against the internal ledger every day — looking for mismatches, duplicate payments, and suspicious transactions. The process is slow, error-prone, and doesn't scale. The goal is an AI system that:

- Automatically matches the majority of transactions with high confidence
- Surfaces only genuinely ambiguous/suspicious cases for human review
- Backs every decision with explainability (why a match/flag happened)
- Never auto-writes anything permanent when confidence is low (human-in-the-loop)

---

## 2. Success Criteria (Definition of Done)

| Metric | Target |
|---|---|
| % of transactions auto-matched (high confidence) | ≥ 70% on synthetic dataset |
| False positive rate on flags | Known and measured (goal isn't 0%, goal is transparency) |
| Every decision has an audit trail | 100% |
| LLM API is called only when needed (not on every transaction) | Rule-based tier filters out the majority of transactions |
| System has a working demo (UI + API) | Yes |
| Test coverage on core logic | ≥ 15 tests (similar standard to Pickup-Line) |

---

## 3. Functional Requirements

### 3.1 Ingestion & Normalization
- Read two CSV sources: `bank_statement.csv` and `internal_ledger.csv`
- Schema for each: `transaction_id, date, amount, currency, description, counterparty`
- Normalization:
  - Unify dates (to ISO 8601)
  - Currency conversion where needed (fixed-rate mock, not real-time API — out of scope)
  - Merchant description cleanup (regex-based: remove trailing IDs, normalize case)
- Output: two lists of normalized `Transaction` objects, each with its own `source` field (`bank` / `ledger`)

### 3.2 Matching Engine (Two-Tier)

**Tier 1 — Deterministic (rule-based, free, fast):**
- Exact match on amount (± 0.01 tolerance for floating-point) + date (± 1 day window)
- If both match → `status: matched`, `confidence: 1.0`, `method: exact_rule`

**Tier 2 — Semantic (LLM/embedding-based, expensive, slow, used only after Tier 1 fails):**
- For remaining unmatched transactions: generate an embedding on the description field (OpenAI/Gemini embedding API or local sentence-transformers — a local model is recommended to save cost)
- Cosine similarity search in pgvector, find the best candidate above a threshold (e.g. > 0.85)
- If a candidate is found and amount/date are also close → `status: matched`, `confidence: similarity_score`, `method: semantic_match`
- Transactions still unmatched after this → move to the Anomaly Scoring Agent

**Routing principle (mirroring model-quality-floor's logic):**
- After Tier 1, only a small fraction of the dataset (~10-20%) should reach Tier 2 — this is a metric to prove out in the report

### 3.3 Anomaly Scoring Agent
- Input: every transaction that failed to match in Tier 1/2
- The agent (LLM call, structured JSON output) evaluates:
  - `risk_score` (0-1)
  - `risk_factors`: list of possible reasons (duplicate_payment, unusual_amount, off_hours, unknown_counterparty, currency_mismatch)
  - `explanation`: one-sentence human-readable justification
- The prompt must be structured/schema-constrained (JSON mode or function calling), not free text
- Stateful element (similar to Pickup-Line): if the same counterparty was already flagged earlier in the run, that context is passed to the agent on the next pass (simple session/context memory, not full DB history — not required for the MVP)

### 3.4 Explainability + Audit Trail
- Every decision (match or flag) is stored in the `decisions` table:
  - `transaction_id`, `decision`, `method` (exact_rule / semantic_match / llm_agent), `confidence`, `reasoning` (raw text/JSON), `timestamp`, `model_used` (if an LLM was involved)
- API endpoint that returns the full decision history for any transaction (`GET /decisions/{transaction_id}`)

### 3.5 Human-in-the-loop Confirm Layer
- Transactions with `confidence < 0.7` (configurable threshold) → status `pending_review`, never auto-set to `matched`/`resolved`
- Separate "Needs Review" view in the UI — a human sees the agent's stated reason/confidence and clicks Approve / Reject / Manual-match
- Approve/Reject actions write to the `decisions` table who (mock user) and when confirmed it — this creates a fully auditable history

### 3.6 Integration Layer — n8n Orchestration + CRM Output

**Principle:** all AI logic (matching, scoring, routing) stays in Python/FastAPI — n8n is purely the "glue" connecting it to real business tools, not a replacement for the logic.

- New endpoint: `POST /webhook/decision` — fired automatically whenever a transaction transitions to `flagged` or `pending_review` (internal call from `reconcile/run`, or a separate polling job)
- Payload includes: `transaction_id, decision, confidence, risk_factors, reasoning, method`
- **n8n workflow:**
  1. Webhook trigger receives the payload above
  2. Field mapping node — transaction data is formatted to match CRM fields
  3. Write node — writes to Airtable (table: "Review Queue") or HubSpot (custom object/deal), with fields: `Transaction ID, Amount, Risk Score, Risk Factors, AI Reasoning, Status, Assigned To`
  4. Conditional node — if `risk_score > 0.8`, also sends a Slack notification to the relevant channel
  5. (Optional) Approve/Reject buttons in Slack that write back to `POST /review/{tx_id}` — a fully closed-loop automation

**Why this is worth showing:**
- Demonstrates that the AI decision doesn't get "lost" in an isolated script, but integrates into real operational infrastructure that a non-technical team actually uses
- An n8n workflow screenshot works very well visually in a LinkedIn post — alongside the code
- Demonstrates clean API design (webhook-ready structure)

**Added deliverable:** n8n workflow export (`.json`) in the repo + screenshot in the README, in its own "Integration Layer" section.

### 3.7 Metrics Dashboard
- A page showing:
  - Total transactions / auto-matched % / pending review % / flagged as anomaly %
  - Breakdown by method (what % resolved by Tier1 vs Tier2 vs the agent)
  - Estimated cost (number of LLM calls × mock $/call) vs. estimated manual-labor cost savings (assumption-based, clearly labeled as such)
  - False positive rate (if the synthetic dataset has built-in ground-truth labels)

---

## 4. Tech Stack (recommended, based on your existing experience)

| Layer | Technology |
|---|---|
| Backend | Python, FastAPI |
| DB | PostgreSQL + pgvector extension |
| Embedding | sentence-transformers (local, free) or OpenAI embeddings API |
| LLM (anomaly agent) | Claude or Gemini — reuse model-quality-floor's `ModelProvider` interface, try both providers |
| Frontend | React + TypeScript (Vite), Recharts for the dashboard |
| Tests | pytest, mypy, ruff (your model-quality-floor standard) |
| Deployment | Railway/Render (backend) + Vercel (frontend) — your Freeside/nile pattern |
| Data | Synthetic generator (Faker) or Kaggle PaySim dataset |
| Orchestration/CRM | n8n (self-host or cloud free tier) + Airtable or HubSpot (free tier) |

---

## 5. Data Model (simplified schema)

```
transactions
- id (uuid)
- source (enum: bank | ledger)
- date (date)
- amount (numeric)
- currency (varchar)
- description (text)
- counterparty (text)
- embedding (vector, nullable — computed only in Tier 2)

decisions
- id (uuid)
- transaction_id (fk)
- matched_transaction_id (fk, nullable)
- decision (enum: matched | flagged | pending_review)
- method (enum: exact_rule | semantic_match | llm_agent | human_override)
- confidence (float)
- reasoning (jsonb)
- model_used (varchar, nullable)
- reviewed_by (varchar, nullable)
- created_at (timestamp)
```

---

## 6. API Endpoints (minimal)

```
POST /ingest              — upload the two CSVs, normalize, write to DB
POST /reconcile/run       — run the full pipeline (Tier1 → Tier2 → agent)
GET  /transactions        — with filters (status, source, date range)
GET  /decisions/{tx_id}   — full audit trail for a specific transaction
POST /review/{tx_id}      — human decision (approve/reject/manual-match)
GET  /metrics             — dashboard data
POST /webhook/decision    — fired on flagged/pending_review status, for n8n
```

---

## 7. Non-Functional Requirements

- **Explainability > accuracy:** if the agent can't justify a decision in structured form, it should return low confidence rather than an overconfident flag
- **Cost awareness:** log every LLM/embedding call — total spend should be visible on the dashboard
- **Idempotency:** re-running `reconcile/run` should not create duplicate decisions
- **Test coverage:** at minimum on the Tier 1 matching logic, the confidence threshold logic, and the happy path of the API endpoints

---

## 8. Milestone Plan (2 weeks)

**Week 1:**
- Day 1-2: Synthetic data generator + ingestion + normalization
- Day 3-4: Tier 1 (rule-based) matching engine + tests
- Day 5: Tier 2 (embedding/pgvector) matching + tests

**Week 2:**
- Day 6-7: Anomaly Scoring Agent (LLM integration, structured output)
- Day 8: Audit trail + decisions API + webhook endpoint
- Day 9: Human-in-the-loop review UI + confirm layer
- Day 10: n8n workflow (webhook → Airtable/HubSpot → Slack) + screenshot
- Day 11: Metrics dashboard + README + demo video/GIF for LinkedIn

---

## 9. Deliverables

1. GitHub repo — clean README (problem → architecture → metrics → limitations, in the model-quality-floor style)
2. Working demo (deployed backend + frontend)
3. n8n workflow export (`.json`) + screenshot — "Integration Layer" section in the README
4. Short demo GIF/video (30-60s) for the LinkedIn post
5. Metrics report — concrete numbers (% auto-matched, cost per reconciliation, false positive rate)

---

## 10. Risks / Known Limitations (state clearly in the README)

- Synthetic data ≠ production data — performance may differ on a real dataset
- The anomaly agent's false positive rate is not tuned to production level — this is a portfolio demo, not a production compliance system
- Currency conversion — mock/fixed rate, not real-time
