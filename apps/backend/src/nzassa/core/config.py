"""Configuration centralisée basée sur pydantic-settings.

Toutes les valeurs proviennent de variables d'environnement (fichier .env en
développement). Aucun secret n'est stocké dans le code.
"""

from functools import lru_cache
from typing import Literal

from pydantic import field_validator
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", env_file_encoding="utf-8", extra="ignore")

    # Général
    nzassa_env: Literal["development", "staging", "production", "test"] = "development"
    nzassa_debug: bool = False
    api_v1_prefix: str = "/api/v1"
    app_name: str = "N'Zassa Business API"

    # Base de données
    database_url: str = "postgresql+asyncpg://nzassa:nzassa_dev@localhost:5432/nzassa"
    database_url_test: str = "postgresql+asyncpg://nzassa:nzassa_dev@localhost:5432/nzassa_test"
    database_echo: bool = False

    # Redis
    redis_url: str = "redis://localhost:6379/0"

    # Sécurité
    secret_key: str = "dev-only-secret-key-change-me-not-for-production"
    jwt_algorithm: str = "HS256"
    access_token_expire_minutes: int = 15
    refresh_token_expire_days: int = 30
    password_reset_expire_minutes: int = 30
    otp_expire_minutes: int = 10
    max_login_attempts: int = 5
    lockout_minutes: int = 15

    # CORS
    cors_origins: list[str] = ["http://localhost:4200"]

    # Rate limiting
    rate_limit_per_minute: int = 120
    auth_rate_limit_per_minute: int = 10

    # Stockage
    storage_backend: Literal["local", "s3"] = "local"
    storage_local_path: str = "./storage"
    max_upload_size_mb: int = 10

    # Emails
    email_backend: Literal["console", "smtp"] = "console"
    email_from: str = "no-reply@nzassa.app"

    # IA
    ai_provider: Literal["stub", "anthropic"] = "stub"
    ai_api_key: str = ""

    # Observabilité
    sentry_dsn: str = ""
    log_level: str = "INFO"

    @field_validator("cors_origins", mode="before")
    @classmethod
    def _split_origins(cls, v: object) -> object:
        if isinstance(v, str):
            return [origin.strip() for origin in v.split(",") if origin.strip()]
        return v

    @property
    def is_production(self) -> bool:
        return self.nzassa_env == "production"


@lru_cache
def get_settings() -> Settings:
    return Settings()
