from functools import lru_cache
from pathlib import Path

from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", extra="ignore")

    app_name: str = "Parakh"
    env: str = "dev"
    secret_key: str = "change-me-in-production"
    database_url: str = "sqlite:///./parakh.db"
    use_sqlite: bool = True
    storage_root: Path = Path("./data/storage")
    cors_origins: str = "http://127.0.0.1:5173,http://localhost:5173"
    retention_days: int = 365
    access_token_expire_minutes: int = 480
    local_llm_provider: str = "stub"
    embedding_provider: str = "local-hash"
    demo_admin_username: str = "admin"
    demo_admin_password: str | None = None
    log_level: str = "INFO"

    @property
    def is_production(self) -> bool:
        return self.env.lower() in {"prod", "production"}

    @property
    def cors_origin_list(self) -> list[str]:
        return [origin.strip() for origin in self.cors_origins.split(",") if origin.strip()]


@lru_cache
def get_settings() -> Settings:
    return Settings()
