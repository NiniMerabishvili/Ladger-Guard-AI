# Architecture

All AI and business logic lives in **FastAPI**. **n8n** is glue to **ClickUp** only (not a replacement for matching or scoring).

```
React/Vite  →  FastAPI (Ingestion → Tier 1 → Tier 2 → Anomaly Agent → Decisions)
                     │
                     ▼ webhook
                    n8n → ClickUp
                     │
              PostgreSQL + pgvector
```

| Stage | Role |
|---|---|
| Tier 1 | Deterministic amount + date match |
| Tier 2 | Embeddings + pgvector for leftovers |
| Anomaly agent | Structured LLM risk score |
| Decisions | Append-only audit rows (`matching_run_id` for idempotency) |

See also the diagram in [AI_Reconciliation_Copilot_Implementation_Plan_EN.md](../AI_Reconciliation_Copilot_Implementation_Plan_EN.md) (section 0) and the root [README.md](../README.md).
