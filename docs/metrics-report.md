# Metrics Report

Filled from `GET /metrics` after ingest + `reconcile/run` on the synthetic (or seeded) dataset.

| Metric | Value | Notes |
|---|---|---|
| Auto-matched % | *run `/metrics`* | Target ≥ 70% on synthetic data |
| Pending review % | *run `/metrics`* | Confidence &lt; 0.7 |
| Flagged % | *run `/metrics`* | High agent risk |
| Method breakdown | exact_rule / semantic_match / llm_agent / human_override | From `decisions.method` |
| Estimated AI cost (USD) | *run `/metrics`* | Mock $/call via `cost_tracker` |
| Labor savings (USD) | *run `/metrics`* | Assumption $2.50 / auto-match |
| False positive rate | `null` until measured | Not production-tuned |

```bash
curl -s http://localhost:8000/metrics | python -m json.tool
```

Paste a real run into this table before portfolio demos.
