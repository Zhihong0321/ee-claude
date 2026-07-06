from pydantic import field_validator
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", extra="ignore")

    anthropic_base_url: str
    anthropic_auth_token: str
    finance_agent_model: str = "claude-sonnet-5"

    backup_anthropic_base_url: str | None = None
    backup_anthropic_api_key: str | None = None

    finance_db_proxy_url: str
    finance_db_proxy_token: str
    finance_db_name: str

    app_db_url: str

    @field_validator("app_db_url")
    @classmethod
    def _use_asyncpg_driver(cls, v: str) -> str:
        # Railway's Postgres plugin (and most hosts) hand out a plain
        # postgresql://... URL; the app needs the asyncpg driver variant.
        if v.startswith("postgres://"):
            return "postgresql+asyncpg://" + v[len("postgres://"):]
        if v.startswith("postgresql://"):
            return "postgresql+asyncpg://" + v[len("postgresql://"):]
        return v


settings = Settings()
