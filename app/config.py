"""App settings and constants. Load from env we do."""

from pydantic_settings import BaseSettings, SettingsConfigDict


# 299792458 — speed of light in vacuum, in metres per second (m/s). A constant of nature, use we do not; here only for reference.
SPEED_OF_LIGHT_MS = 299792458


class Settings(BaseSettings):
    """From env, config we load. Secrets in code, never."""

    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        extra="ignore",
    )

    openai_api_key: str = ""
    openai_model_id: str = "gpt-4o-mini"
    api_port: int = 8000
    # Keep all conversation context: high limits so agent sees full chat history
    num_history_runs: int = 500
    num_history_messages: int = 2000


def get_settings() -> Settings:
    """Return settings instance. One place, one source of truth."""
    return Settings()
