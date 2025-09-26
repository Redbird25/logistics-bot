from functools import lru_cache
from pathlib import Path

from pydantic import Field, field_validator
from pydantic_settings import BaseSettings

BASE_DIR = Path(__file__).resolve().parents[2]


class AppSettings(BaseSettings):
    tg_bot_token: str | None = Field(None, alias="TG_BOT_TOKEN")
    tg_api_id: int | None = Field(None, alias="TG_API_ID")
    tg_api_hash: str | None = Field(None, alias="TG_API_HASH")
    tg_session_string: str | None = Field(None, alias="TG_SESSION_STRING")

    postgres_host: str = Field("db", alias="POSTGRES_HOST")
    postgres_port: int = Field(5432, alias="POSTGRES_PORT")
    postgres_db: str = Field("logi", alias="POSTGRES_DB")
    postgres_user: str = Field("logi", alias="POSTGRES_USER")
    postgres_password: str = Field("logi", alias="POSTGRES_PASSWORD")

    redis_host: str = Field("redis", alias="REDIS_HOST")
    redis_port: int = Field(6379, alias="REDIS_PORT")
    redis_db: int = Field(0, alias="REDIS_DB")

    retention_days: int = Field(3, alias="RETENTION_DAYS")
    max_results_per_query: int = Field(20, alias="MAX_RESULTS_PER_QUERY")
    similarity_threshold: float = Field(0.85, alias="SIMILARITY_THRESHOLD")

    class Config:
        env_file = BASE_DIR / ".env"
        env_file_encoding = "utf-8"
        populate_by_name = True

    @field_validator("tg_bot_token", "tg_api_hash", mode="before")
    @classmethod
    def _empty_str_to_none(cls, value: str | None) -> str | None:
        if isinstance(value, str) and not value.strip():
            return None
        return value

    @field_validator("tg_session_string", mode="before")
    @classmethod
    def _blank_session_to_none(cls, value: str | None) -> str | None:
        if isinstance(value, str) and not value.strip():
            return None
        return value

    @field_validator("tg_api_id", mode="before")
    @classmethod
    def _parse_tg_api_id(cls, value: str | int | None) -> int | None:
        if isinstance(value, str):
            value = value.strip()
            if not value:
                return None
        return value

    @property
    def postgres_dsn(self) -> str:
        return (
            f"postgresql+asyncpg://{self.postgres_user}:{self.postgres_password}"
            f"@{self.postgres_host}:{self.postgres_port}/{self.postgres_db}"
        )

    @property
    def redis_url(self) -> str:
        return f"redis://{self.redis_host}:{self.redis_port}/{self.redis_db}"


@lru_cache(maxsize=1)
def get_settings() -> AppSettings:
    return AppSettings()

