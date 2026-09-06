"""Environment variables and application settings (pydantic-settings)."""

from pathlib import Path

from pydantic_settings import BaseSettings, SettingsConfigDict

_BACKEND_DIR = Path(__file__).resolve().parents[1]


class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_file=str(_BACKEND_DIR / ".env"),
        env_file_encoding="utf-8",
        extra="ignore",
    )

    DATABASE_URL: str = "postgresql+psycopg://postgres:postgres@localhost:5432/reconciliation"
    REVIEW_CONFIDENCE_THRESHOLD: float = 0.7
    N8N_WEBHOOK_URL: str = "http://localhost:5678/webhook/decision"
    N8N_WEBHOOK_SECRET: str = ""

    # Comma-separated browser origins allowed to call the API (local + Vercel).
    CORS_ORIGINS: str = "http://localhost:5173,http://127.0.0.1:5173"

    EMBEDDING_PROVIDER: str = "local"  # local | openai
    LLM_PROVIDER: str = "gemini"  # claude | gemini
    # Cap live LLM calls per reconcile so Upload & run finishes in seconds.
    # Remaining leftovers use a fast local heuristic (still method=llm_agent).
    LLM_MAX_PER_RUN: int = 2

    ANTHROPIC_API_KEY: str = ""
    GOOGLE_API_KEY: str = ""
    OPENAI_API_KEY: str = ""

    @property
    def cors_origin_list(self) -> list[str]:
        return [origin.strip() for origin in self.CORS_ORIGINS.split(",") if origin.strip()]


settings = Settings()
