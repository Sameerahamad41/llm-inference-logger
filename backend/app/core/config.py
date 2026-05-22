"""Application configuration loaded from environment variables."""

from pydantic_settings import BaseSettings


class Settings(BaseSettings):
    # --- Application ---
    APP_NAME: str = "LLM Inference Logger"
    DEBUG: bool = False

    # --- Database ---
    DATABASE_URL: str = "postgresql+asyncpg://postgres:postgres@db:5432/inference_logger"
    DATABASE_URL_SYNC: str = "postgresql://postgres:postgres@db:5432/inference_logger"

    # --- LLM Provider API Keys (at least one required) ---
    OPENAI_API_KEY: str = ""
    ANTHROPIC_API_KEY: str = ""
    GOOGLE_API_KEY: str = ""

    # --- Default model selection ---
    DEFAULT_PROVIDER: str = "openai"
    DEFAULT_MODEL: str = "gpt-4.1-nano"

    # --- Ingestion ---
    INGESTION_BATCH_SIZE: int = 50
    INGESTION_FLUSH_INTERVAL_SECONDS: float = 2.0

    # --- PII Redaction ---
    PII_REDACTION_ENABLED: bool = True

    class Config:
        env_file = ".env"
        case_sensitive = True


settings = Settings()
