import logging
from functools import lru_cache
from pathlib import Path

from pydantic import Field
from pydantic_settings import BaseSettings, SettingsConfigDict

logger = logging.getLogger(__name__)

PROJECT_ROOT = Path(__file__).resolve().parent.parent
DATA_DIR = PROJECT_ROOT / "data"


class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        extra="ignore",
    )

    openai_api_key: str | None = Field(
        default=None,
        description="OpenAI API key; omit to use deterministic offline RCA mode",
    )
    slack_webhook_url: str | None = None
    llm_model: str = "gpt-4o"

    chroma_db_path: str = str(DATA_DIR / "chroma")
    incident_history_db_path: str = str(DATA_DIR / "incidents.db")

    company_hourly_revenue: float = 125_000.0
    engineering_hourly_cost: float = 350.0
    default_downtime_minutes: float = 45.0

    service_revenue_weight_payment_api: float = 0.55
    service_revenue_weight_user_service: float = 0.30
    service_revenue_weight_default: float = 0.15

    api_host: str = "0.0.0.0"
    api_port: int = 8000


@lru_cache
def get_settings() -> Settings:
    DATA_DIR.mkdir(parents=True, exist_ok=True)
    try:
        return Settings()
    except Exception as exc:
        logger.warning(
            "Settings validation issue (%s); using safe defaults where possible",
            exc,
        )
        return Settings.model_construct(
            openai_api_key=None,
            slack_webhook_url=None,
        )


settings = get_settings()
