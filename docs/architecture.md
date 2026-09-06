# Architecture

See the high-level diagram in the implementation plan (section 0).

All AI and business logic lives in FastAPI. n8n is glue to Airtable and Slack only.

```
React/Vite  →  FastAPI (Ingestion → Tier 1 → Tier 2 → Anomaly Agent → Decisions)
                     │
                     ▼ webhook
                    n8n → Airtable / Slack
                     │
              PostgreSQL + pgvector
```
