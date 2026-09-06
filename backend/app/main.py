"""FastAPI entrypoint."""

from collections.abc import AsyncIterator
from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.config import settings
from app.routes import (
    decisions,
    ingest,
    metrics,
    projects,
    reconcile,
    review,
    transactions,
    webhook,
)


def _warm_embedding_model() -> None:
    """Load SentenceTransformer once at startup so the first reconcile is fast."""
    if settings.EMBEDDING_PROVIDER.lower() != "local":
        return
    try:
        from app.matching.embedding_provider import get_embedding_provider

        get_embedding_provider().embed("warmup")
    except Exception:
        # Non-fatal — first reconcile will load the model instead.
        pass


@asynccontextmanager
async def lifespan(_app: FastAPI) -> AsyncIterator[None]:
    import asyncio

    await asyncio.to_thread(_warm_embedding_model)
    yield


app = FastAPI(
    title="AI Reconciliation Copilot",
    version="0.1.0",
    lifespan=lifespan,
)
app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.cors_origin_list,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


@app.get("/health")
def health() -> dict[str, str]:
    return {"status": "ok"}


app.include_router(ingest.router)
app.include_router(reconcile.router)
app.include_router(projects.router)
app.include_router(transactions.router)
app.include_router(decisions.router)
app.include_router(review.router)
app.include_router(metrics.router)
app.include_router(webhook.router)
