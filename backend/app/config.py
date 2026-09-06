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

    EMBEDDING_PROVIDER: str = "local"  # local | openai
    LLM_PROVIDER: str = "claude"  # claude | gemini

    ANTHROPIC_API_KEY: str = ""
    GOOGLE_API_KEY: str = ""
    OPENAI_API_KEY: str = ""


settings = Settings()
