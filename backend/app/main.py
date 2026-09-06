"""FastAPI entrypoint."""

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.routes import (
    decisions,
    ingest,
    metrics,
    reconcile,
    review,
    transactions,
    webhook,
)

app = FastAPI(
    title="AI Reconciliation Copilot",
    version="0.1.0",
)
app.add_middleware(
    CORSMiddleware,
    allow_origins=[
        "http://localhost:5173",
        "http://127.0.0.1:5173",
    ],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


@app.get("/health")
def health() -> dict[str, str]:
    return {"status": "ok"}


app.include_router(ingest.router)
app.include_router(reconcile.router)
app.include_router(transactions.router)
app.include_router(decisions.router)
app.include_router(review.router)
app.include_router(metrics.router)
app.include_router(webhook.router)
