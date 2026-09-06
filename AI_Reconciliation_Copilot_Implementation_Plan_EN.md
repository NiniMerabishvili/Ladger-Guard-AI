# AI Reconciliation & Anomaly Triage Copilot — Detailed Implementation Plan

**Version:** v1.0
**Duration:** 2 weeks (MVP)
**Source:** AI_Reconciliation_Copilot_TechSpec_EN.md

This document is a step-by-step build plan — every section of the tech spec is turned into concrete, executable tasks, with code structure, file names, and acceptance criteria.

---

## 0. High-Level Architecture

```
┌─────────────────┐      ┌──────────────────────────────────────────┐
│   React/Vite     │      │              FastAPI Backend               │
│   Frontend       │◄────►│                                            │
│  (Dashboard,     │ REST │  ┌──────────┐  ┌──────────┐  ┌──────────┐ │
│   Review UI)     │      │  │ Ingestion│─►│ Tier 1   │─►│ Tier 2   │ │
└──────────────────┘      │  │ /Normal. │  │ (rules)  │  │ (vector) │ │
                           │  └──────────┘  └──────────┘  └────┬─────┘ │
                           │                                    │       │
                           │                            ┌───────▼────┐ │
                           │                            │  Anomaly   │ │
                           │                            │  Agent(LLM)│ │
                           │                            └───────┬────┘ │
                           │                                    │       │
                           │                            ┌───────▼────┐ │
                           │                            │  Decisions │ │
                           │                            │  + Audit   │ │
                           │                            └───────┬────┘ │
                           └────────────────────────────────────┼──────┘
                                                                 │ webhook
                                                        ┌────────▼────────┐
                                                        │      n8n        │
                                                        │ Webhook→Airtable │
                                                        │   →Slack alert   │
                                                        └──────────────────┘
                    ┌──────────────────┐
                    │ PostgreSQL +      │
                    │ pgvector          │
                    └──────────────────┘
```

**Core principle:** all AI/business logic lives in FastAPI. n8n is purely the "glue" to external systems (Airtable/Slack) — not a replacement for the logic.

---

## 1. Repository Structure

```
ai-reconciliation-copilot/
├── backend/
│   ├── app/
│   │   ├── main.py                  # FastAPI entrypoint
│   │   ├── config.py                # env vars, settings (pydantic-settings)
│   │   ├── db/
│   │   │   ├── session.py           # SQLAlchemy engine/session
│   │   │   ├── models.py            # Transaction, Decision ORM models
│   │   │   └── migrations/          # alembic
│   │   ├── schemas/
│   │   │   ├── transaction.py       # pydantic schemas
│   │   │   ├── decision.py
│   │   │   └── metrics.py
│   │   ├── ingestion/
│   │   │   ├── csv_loader.py
│   │   │   └── normalizer.py        # date/currency/description cleanup
│   │   ├── matching/
│   │   │   ├── tier1_rules.py       # deterministic exact match
│   │   │   ├── tier2_semantic.py    # embeddings + pgvector search
│   │   │   └── embedding_provider.py# local (sentence-transformers) or API
│   │   ├── agent/
│   │   │   ├── anomaly_agent.py     # LLM call, structured JSON output
│   │   │   ├── model_provider.py    # reused from model-quality-floor
│   │   │   └── prompts.py
│   │   ├── routes/
│   │   │   ├── ingest.py
│   │   │   ├── reconcile.py
│   │   │   ├── transactions.py
│   │   │   ├── decisions.py
│   │   │   ├── review.py
│   │   │   ├── metrics.py
│   │   │   └── webhook.py
│   │   ├── services/
│   │   │   ├── reconciliation_service.py  # orchestrates Tier1→Tier2→Agent
│   │   │   ├── audit_service.py
│   │   │   └── cost_tracker.py
│   │   └── core/
│   │       ├── logging.py
│   │       └── exceptions.py
│   ├── tests/
│   │   ├── test_tier1_matching.py
│   │   ├── test_tier2_matching.py
│   │   ├── test_anomaly_agent.py
│   │   ├── test_confidence_threshold.py
│   │   ├── test_idempotency.py
│   │   ├── test_api_endpoints.py
│   │   └── conftest.py
│   ├── scripts/
│   │   └── generate_synthetic_data.py  # Faker-based generator
│   ├── data/
│   │   ├── bank_statement.csv
│   │   └── internal_ledger.csv
│   ├── pyproject.toml               # deps, ruff, mypy config
│   ├── Dockerfile
│   └── .env.example
├── frontend/
│   ├── src/
│   │   ├── pages/
│   │   │   ├── Dashboard.tsx
│   │   │   ├── ReviewQueue.tsx
│   │   │   └── TransactionDetail.tsx
│   │   ├── components/
│   │   │   ├── MetricsCards.tsx
│   │   │   ├── MethodBreakdownChart.tsx
│   │   │   ├── ReviewCard.tsx
│   │   │   └── AuditTrailTimeline.tsx
│   │   ├── api/client.ts
│   │   └── types.ts
│   ├── package.json
│   └── vite.config.ts
├── n8n/
│   ├── reconciliation-workflow.json
│   └── screenshot.png
├── docs/
│   ├── architecture.md
│   └── metrics-report.md
├── README.md
└── docker-compose.yml               # postgres+pgvector, backend, n8n
```

---

## 2. Database (PostgreSQL + pgvector)

### 2.1 Environment setup
- In `docker-compose.yml`, use the `ankane/pgvector` or `pgvector/pgvector:pg16` image.
- Enable the extension: `CREATE EXTENSION IF NOT EXISTS vector;`

### 2.2 Schema (Alembic migration)

```sql
CREATE TYPE source_enum AS ENUM ('bank', 'ledger');
CREATE TYPE decision_enum AS ENUM ('matched', 'flagged', 'pending_review');
CREATE TYPE method_enum AS ENUM ('exact_rule', 'semantic_match', 'llm_agent', 'human_override');

CREATE TABLE transactions (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    source source_enum NOT NULL,
    date DATE NOT NULL,
    amount NUMERIC(14,2) NOT NULL,
    currency VARCHAR(3) NOT NULL,
    description TEXT NOT NULL,
    counterparty TEXT,
    embedding VECTOR(384),  -- 384 for all-MiniLM-L6-v2, adjust to model
    status VARCHAR(20) DEFAULT 'unmatched',
    created_at TIMESTAMP DEFAULT now()
);

CREATE TABLE decisions (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    transaction_id UUID REFERENCES transactions(id),
    matched_transaction_id UUID REFERENCES transactions(id) NULL,
    decision decision_enum NOT NULL,
    method method_enum NOT NULL,
    confidence FLOAT NOT NULL,
    reasoning JSONB,
    model_used VARCHAR(50),
    reviewed_by VARCHAR(100),
    created_at TIMESTAMP DEFAULT now()
);

CREATE INDEX idx_transactions_embedding ON transactions
    USING ivfflat (embedding vector_cosine_ops) WITH (lists = 100);
CREATE INDEX idx_decisions_tx ON decisions(transaction_id);
```

**Tip:** also add a `matching_run_id` column to `decisions` — useful for checking idempotency (see 7.3).

---

## 3. Backend — Step-by-Step Build

### 3.1 Ingestion & Normalization (`ingestion/`)

**`csv_loader.py`:**
- Read both CSVs (pandas or the csv module)
- Validate: presence of all required columns (`transaction_id, date, amount, currency, description, counterparty`)

**`normalizer.py`:**
- Dates → ISO 8601 (`dateutil.parser` + validation)
- Currency conversion → fixed-rate dict, e.g. `{"EUR": 1.08, "GBP": 1.27}` normalized to USD (mock, with a comment noting a real-time API would be needed in production)
- Description cleanup — regex rules:
  - `re.sub(r'\d{6,}', '', desc)` — strip long numeric IDs
  - `.strip().upper()` or `.title()` for case normalization
  - Strip trailing merchant suffixes (`" REF#12345"`, `" *POS"`, etc.)

**Output:** `List[TransactionCreate]` pydantic objects, each with a `source` field.

**Tests:** `test_normalizer.py` — date format variants, currency conversion, description cleanup edge cases.

### 3.2 Tier 1 — Deterministic Matching (`matching/tier1_rules.py`)

Logic:
```python
def try_exact_match(bank_tx, ledger_candidates, amount_tol=0.01, date_window_days=1):
    for ledger_tx in ledger_candidates:
        if abs(bank_tx.amount - ledger_tx.amount) <= amount_tol \
           and abs((bank_tx.date - ledger_tx.date).days) <= date_window_days:
            return MatchResult(
                matched=True, confidence=1.0, method="exact_rule",
                matched_id=ledger_tx.id
            )
    return MatchResult(matched=False)
```

**Optimization:** avoid an O(n²) loop on large datasets — indexing by rounded amount (dict/bucket) will help once you cross ~1,000 transactions.

**Tests (at least 5):**
1. Exact match (identical amount+date)
2. Floating-point tolerance (0.005 difference → still matches)
3. Date window edge case (±1 day)
4. Amount outside tolerance → no match
5. Date outside window → no match

### 3.3 Tier 2 — Semantic Matching (`matching/tier2_semantic.py`, `embedding_provider.py`)

**Embedding provider — abstraction:**
```python
class EmbeddingProvider(Protocol):
    def embed(self, text: str) -> list[float]: ...

class LocalSentenceTransformerProvider:
    # sentence-transformers/all-MiniLM-L6-v2 — free, fast, 384-dim
    ...

class OpenAIEmbeddingProvider:
    # text-embedding-3-small, for fallback/comparison
    ...
```
Recommendation: default to the local model (to save cost), with an env var to switch to the API.

**Writing to pgvector:** compute embeddings for Tier 1's unmatched transactions first, and store them in `transactions.embedding`.

**Search query:**
```sql
SELECT id, description, amount, date,
       1 - (embedding <=> :query_embedding) AS similarity
FROM transactions
WHERE source = :opposite_source AND status = 'unmatched'
ORDER BY embedding <=> :query_embedding
LIMIT 5;
```

**Logic:**
- If the best candidate's similarity > 0.85 **and** amount/date are close (wider tolerance, e.g. ±3%, ±3 days) → `matched`, `confidence = similarity_score`, `method = semantic_match`
- Otherwise → passes to the Anomaly Agent

**Tests:** use a mocked embedding provider (fixed vectors) — verify threshold logic without making real embedding calls (fast, deterministic tests).

### 3.4 Anomaly Scoring Agent (`agent/anomaly_agent.py`)

**Structured output prompt (schema-constrained):**
```python
ANOMALY_SCHEMA = {
    "type": "object",
    "properties": {
        "risk_score": {"type": "number", "minimum": 0, "maximum": 1},
        "risk_factors": {
            "type": "array",
            "items": {"enum": [
                "duplicate_payment", "unusual_amount",
                "off_hours", "unknown_counterparty", "currency_mismatch"
            ]}
        },
        "explanation": {"type": "string"}
    },
    "required": ["risk_score", "risk_factors", "explanation"]
}
```

**`model_provider.py`:** port over the model-quality-floor `ModelProvider` interface — a uniform interface for calling Claude and Gemini (`.generate_structured(prompt, schema)`).

**Session/context memory (stateful element):**
```python
class RunContext:
    def __init__(self):
        self.flagged_counterparties: dict[str, list[str]] = {}

    def note_flag(self, counterparty: str, reason: str):
        self.flagged_counterparties.setdefault(counterparty, []).append(reason)

    def get_prior_context(self, counterparty: str) -> str | None:
        prior = self.flagged_counterparties.get(counterparty)
        return f"Note: this counterparty was already flagged for: {prior}" if prior else None
```
This context is attached to the prompt whenever the same counterparty has already been flagged earlier in the current run. In-memory, run-scoped — no DB persistence needed for the MVP.

**Fallback logic:** if the LLM's response fails schema validation → default to low confidence + `explanation: "Agent output could not be validated"` — never crash, never surface an overconfident flag.

**Tests:** mock the LLM call — schema validation success/failure, session memory being applied on a second call.

### 3.5 Explainability + Audit Trail (`services/audit_service.py`, `routes/decisions.py`)

- Every Tier1/Tier2/Agent decision is written to the `decisions` table (never overwritten, always a new row → complete history)
- `GET /decisions/{transaction_id}` — every decision row for that transaction, in chronological order

### 3.6 Human-in-the-Loop (`routes/review.py`)

```python
@router.post("/review/{tx_id}")
def review_transaction(tx_id: UUID, action: ReviewAction):
    # action.decision: "approve" | "reject" | "manual_match"
    # action.reviewed_by: mock user string
    # writes a new row to decisions with method="human_override"
    ...
```

**Rule:** `confidence < 0.7` → status is always `pending_review`, never auto-set to `matched`/`resolved`. This threshold should be exposed in `config.py` (`REVIEW_CONFIDENCE_THRESHOLD`).

### 3.7 n8n Integration (`routes/webhook.py`)

**Trigger principle:** after `reconcile/run` completes, for every transaction whose status is `flagged`/`pending_review`, the backend makes a POST call to the n8n webhook URL (not the reverse — n8n does not poll the database).

```python
async def notify_n8n(decision: Decision):
    payload = {
        "transaction_id": str(decision.transaction_id),
        "decision": decision.decision,
        "confidence": decision.confidence,
        "risk_factors": decision.reasoning.get("risk_factors", []),
        "reasoning": decision.reasoning.get("explanation"),
        "method": decision.method,
    }
    async with httpx.AsyncClient() as client:
        await client.post(settings.N8N_WEBHOOK_URL, json=payload, timeout=5)
```

**n8n workflow (built separately in the n8n UI, then exported):**
1. **Webhook node** — receives the payload above
2. **Set/Field Mapping node** — payload → ClickUp fields (`Transaction ID, Amount, Risk Score, Risk Factors, AI Reasoning, Status, Assigned To`)
3. **IF node** — `high_priority` / `risk_score > 0.8` → urgent ClickUp task; else normal-priority task
4. **ClickUp node** — create a task in the "Review Queue" list (replaces Airtable + Slack)

**Tip:** run n8n locally via `docker-compose.yml` (`n8nio/n8n` image), commit the `.json` export to the repo (`n8n/reconciliation-workflow.json`) plus a screenshot for the README.

### 3.8 Metrics Dashboard API (`routes/metrics.py`)

```python
@router.get("/metrics")
def get_metrics():
    return {
        "total_transactions": ...,
        "auto_matched_pct": ...,
        "pending_review_pct": ...,
        "flagged_pct": ...,
        "method_breakdown": {"exact_rule": ..., "semantic_match": ..., "llm_agent": ...},
        "estimated_llm_cost_usd": ...,   # from cost_tracker.py
        "estimated_manual_labor_savings_usd": ...,  # assumption-based, must be clearly labeled as such
        "false_positive_rate": ...,      # if the synthetic dataset has ground-truth labels
    }
```

**`cost_tracker.py`:** log every embedding/LLM call — model used, number of tokens/calls, mock $/call rate → running total spend.

---

## 4. AI Layer — Model Provider Abstraction

```python
class ModelProvider(Protocol):
    async def generate_structured(self, prompt: str, schema: dict) -> dict: ...

class ClaudeProvider(ModelProvider):
    # anthropic SDK, model="claude-sonnet-4-6" or equivalent
    ...

class GeminiProvider(ModelProvider):
    ...
```
- Test both providers on the same set of anomalies → compare results in the README (which one is more accurate/cheaper)
- Retry/timeout logic — if the API fails, the agent should return a low-confidence fallback, not an exception that halts the whole pipeline

---

## 5. Frontend (React + TypeScript + Vite)

### 5.1 Pages
| Page | Components | Purpose |
|---|---|---|
| **Dashboard** | `MetricsCards`, `MethodBreakdownChart` (Recharts pie/bar) | Overall picture: %auto-matched, cost, breakdown |
| **Review Queue** | `ReviewCard` list | pending_review transactions, Approve/Reject/Manual-match buttons |
| **Transaction Detail** | `AuditTrailTimeline` | full decision history for one transaction |

### 5.2 API Client (`api/client.ts`)
- Axios/fetch wrapper for every endpoint
- Type-safe responses (`types.ts` mirroring the backend Pydantic schemas)

### 5.3 UI Flow
1. Review Queue list, each card shows: confidence, risk_factors badges, the agent's explanation
2. Approve → POST `/review/{tx_id}` `{decision: "approve"}`
3. UI updates the status optimistically or via refetch
4. Dashboard auto-refresh or a manual "Refresh" button hitting `/metrics`

**Design tip:** use clear color coding by confidence level (green ≥0.9, yellow 0.7-0.9, red <0.7) — easy to scan even on large tables.

---

## 6. Testing Strategy (at least 15 tests)

| Category | Count | Examples |
|---|---|---|
| Normalization | 3 | date parsing, currency conversion, description regex |
| Tier 1 matching | 5 | exact match, tolerance edges, no-match cases |
| Tier 2 matching | 3 | threshold logic (mocked embeddings) |
| Confidence threshold / review routing | 2 | <0.7 → pending_review, ≥0.7 → matched |
| Agent structured output | 3 | schema validation, fallback on invalid response, session memory |
| API happy path | 4 | `/ingest`, `/reconcile/run`, `/decisions/{id}`, `/review/{id}` |
| Idempotency | 2 | running `reconcile/run` twice → decisions are not duplicated |

**Tools:** `pytest`, `pytest-asyncio` (for async endpoints), `mypy --strict`, `ruff`. Mock all LLM calls everywhere (`unittest.mock` or `respx` for HTTP mocking) — tests should never depend on a real API.

---

## 7. Non-Functional Requirements — Implementation

### 7.1 Explainability > Accuracy
- In the agent prompt, state explicitly: "If you cannot justify with specific evidence, set risk_score low and explain why, rather than guessing."
- Any schema-validation failure → automatically low-confidence, never a high-risk flag

### 7.2 Cost Awareness
- Every embedding/LLM call goes through `cost_tracker.log_call(provider, model, tokens_or_calls)`
- Dashboard shows a running total

### 7.3 Idempotency
```python
def run_reconciliation(run_id: UUID | None = None):
    run_id = run_id or uuid4()
    # every decision row carries a matching_run_id
    # if a transaction already has a non-null 'resolved' status before this run starts,
    # skip it from reprocessing
```
Test: run `reconcile/run` twice on the same data → the `decisions` row count does not increase.

---

## 8. Daily Plan (detailed, based on tech spec section 8)

**Week 1**
- **Day 1:** Repo scaffold, docker-compose (Postgres+pgvector), `pyproject.toml`, Faker-based synthetic data generator (bank_statement.csv, internal_ledger.csv — deliberately inject duplicates, off-by-one dates, amount mismatches for realistic edge cases)
- **Day 2:** Ingestion + Normalization complete + 3 tests
- **Day 3:** DB models + Alembic migration + Tier 1 logic scaffold
- **Day 4:** Finish Tier 1 + 5 tests + `/ingest`, `/reconcile/run` (stub, no Tier2/Agent yet)
- **Day 5:** Embedding provider (local), pgvector integration, Tier 2 logic + 3 tests

**Week 2**
- **Day 6:** ModelProvider abstraction (Claude+Gemini), anomaly agent schema + prompt
- **Day 7:** Session memory, fallback logic, agent tests (mocked)
- **Day 8:** Full write path into `decisions`, `/decisions/{id}`, `/webhook/decision` endpoint
- **Day 9:** Frontend scaffold + Review UI + Approve/Reject → `/review/{tx_id}`
- **Day 10:** Build n8n workflow (webhook→field mapping→Airtable→IF→Slack), export + screenshot
- **Day 11:** Metrics dashboard (frontend+backend), README (problem→architecture→metrics→limitations), record demo GIF

**Buffer time:** leave 2-3 hours at the end of Day 11 for deployment and final bug fixes — this is often where time slips.

---

## 9. Deployment

| Component | Where | Notes |
|---|---|---|
| Backend (FastAPI) | Railway/Render | from `Dockerfile`, with env vars (DB URL, API keys) |
| DB | Railway/Render Postgres add-on (verify pgvector support in advance) | if unsupported, Supabase is a good alternative (native pgvector) |
| Frontend | Vercel | `VITE_API_URL` env var pointing to the deployed backend URL |
| n8n | n8n Cloud free tier or self-hosted on the same Railway project | webhook URL must be publicly reachable |

---

## 10. README Structure (model-quality-floor style)

1. **Problem** — why reconciliation is a pain point
2. **Architecture** — diagram (section 0 above) + brief explanation of Tier1/Tier2/Agent
3. **Metrics** — real numbers: % auto-matched, false positive rate, cost per reconciliation
4. **Integration Layer** — n8n workflow screenshot + explanation
5. **Limitations** — the risks from tech spec section 10, quoted directly
6. **How to run locally** — `docker-compose up`, env setup, seed data
7. **Demo GIF/link**

---

## 11. Final Acceptance Checklist (Definition of Done)

- [ ] ≥70% auto-match rate on the synthetic dataset
- [ ] Only ~10-20% of transactions reach Tier 2 (confirmed by logs/metrics)
- [ ] Every decision has an audit trail row
- [ ] `confidence < 0.7` → never auto-resolved
- [ ] n8n workflow works end-to-end (webhook → Airtable → Slack at minimum)
- [ ] ≥15 tests pass (`pytest`), `mypy`/`ruff` clean
- [ ] Dashboard shows cost and method breakdown
- [ ] README is complete with all required sections
- [ ] Demo is deployed and reachable at a public URL
- [ ] Demo GIF/video ready for LinkedIn

---

## 12. Additional Risks (implementation-level, beyond the tech spec)

- **pgvector availability on hosting:** some managed Postgres tiers (e.g. Railway's base plan) don't include the pgvector extension — Supabase or self-hosted Postgres is the fallback.
- **LLM API rate limits/cost spikes:** make sure Tier 1/Tier 2 filtering is genuinely reducing agent calls during testing, otherwise running large volumes of synthetic data will get expensive.
- **n8n public webhook security:** add a simple secret token header check on `/webhook/decision` so it can't be triggered accidentally by a third party.

---

Every section of this plan is independently startable and testable — you can follow the daily plan (section 8) directly, or work through the sections in order (0→11) at your own pace.
