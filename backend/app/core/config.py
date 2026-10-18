from functools import lru_cache
from pathlib import Path
from zoneinfo import ZoneInfo

from pydantic import field_validator
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_file=(
            Path(__file__).resolve().parents[3] / ".env",
            Path(__file__).resolve().parents[2] / ".env",
        ),
        extra="ignore",
    )

    app_name: str = "Parakh"
    env: str = "dev"
    secret_key: str = "change-me-in-production"
    database_url: str = "sqlite:///./parakh.db"
    use_sqlite: bool = True
    storage_root: Path = Path("./data/storage")
    audit_signing_key_path: Path = Path("./data/storage/keys/audit-ed25519-private.pem")
    cors_origins: str = "http://127.0.0.1:5173,http://localhost:5173,http://127.0.0.1:4173,http://127.0.0.1:5183"
    retention_days: int = 365
    max_upload_bytes: int = 512 * 1024 * 1024
    max_zip_members: int = 1000
    max_zip_uncompressed_bytes: int = 1024 * 1024 * 1024
    max_zip_ratio: int = 100
    access_token_expire_minutes: int = 480
    local_llm_provider: str = "stub"
    embedding_provider: str = "local-hash"
    demo_admin_username: str = "admin"
    demo_admin_password: str | None = None
    whatsapp_timezone: str = "Asia/Kolkata"
    whatsapp_day_first: bool = True
    log_level: str = "INFO"

    @field_validator("demo_admin_password")
    @classmethod
    def demo_password_length(cls, value: str | None) -> str | None:
        if value and len(value.encode("utf-8")) > 72:
            raise ValueError("DEMO_ADMIN_PASSWORD must be at most 72 UTF-8 bytes")
        return value

    @field_validator("whatsapp_timezone")
    @classmethod
    def valid_whatsapp_timezone(cls, value: str) -> str:
        try:
            ZoneInfo(value)
        except (KeyError, ValueError) as exc:
            raise ValueError("WHATSAPP_TIMEZONE must name an installed IANA time zone") from exc
        return value

    @property
    def is_production(self) -> bool:
        return self.env.lower() in {"prod", "production"}

    @property
    def cors_origin_list(self) -> list[str]:
        return [origin.strip() for origin in self.cors_origins.split(",") if origin.strip()]


@lru_cache
def get_settings() -> Settings:
    return Settings()
