from __future__ import annotations

from functools import lru_cache

from pydantic import AliasChoices, Field, SecretStr
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", env_file_encoding="utf-8", extra="ignore")

    app_env: str = "development"
    app_secret_key: SecretStr
    database_url: str
    database_url_sync: str
    mail_credentials_key: SecretStr
    telegram_bot_token: SecretStr | None = None
    telegram_bot_username: str | None = None
    telegram_webhook_secret: SecretStr | None = None
    telegram_webhook_url: str | None = None
    public_base_url: str = "http://localhost:8000"
    imap_host: str | None = None
    imap_port: int = 993
    imap_username: str | None = None
    imap_password: SecretStr | None = None
    imap_label: str = "primary-imap"
    microsoft_oauth_client_id: str | None = Field(
        default=None,
        validation_alias=AliasChoices("MICROSOFT_CLIENT_ID", "MICROSOFT_OAUTH_CLIENT_ID"),
    )
    microsoft_oauth_client_secret: SecretStr | None = Field(
        default=None,
        validation_alias=AliasChoices("MICROSOFT_CLIENT_SECRET", "MICROSOFT_OAUTH_CLIENT_SECRET"),
    )
    microsoft_oauth_tenant: str = Field(
        default="consumers",
        validation_alias=AliasChoices("MICROSOFT_AUTHORITY", "MICROSOFT_OAUTH_TENANT"),
    )
    microsoft_oauth_redirect_uri: str | None = Field(
        default=None,
        validation_alias=AliasChoices("MICROSOFT_REDIRECT_URI", "MICROSOFT_OAUTH_REDIRECT_URI"),
    )
    salla_client_id: str | None = None
    salla_client_secret: SecretStr | None = None
    salla_webhook_secret: SecretStr | None = None
    salla_token_key: SecretStr | None = None
    salla_app_id: str | None = None
    salla_api_verification_enabled: bool = False
    salla_notification_poll_seconds: int = Field(default=60, ge=15, le=3600)
    salla_customer_session_minutes: int = Field(default=60, ge=10, le=240)
    customer_session_minutes: int = Field(default=60, ge=10, le=1440)
    salla_usage_max: int = Field(default=5, ge=1, le=100)
    salla_usage_period_seconds: int = Field(default=86400, ge=60, le=604800)
    salla_usage_cooldown_seconds: int = Field(default=30, ge=0, le=3600)
    cookie_secure: bool = True
    admin_session_hours: int = Field(default=12, ge=1, le=72)
    activation_token_hours: int = Field(default=24, ge=1, le=168)
    verification_wait_seconds: int = Field(default=600, ge=60, le=3600)
    result_retention_seconds: int = Field(default=900, ge=60, le=3600)
    worker_poll_seconds: float = Field(default=2, ge=0.5, le=30)
    log_level: str = "INFO"

    @property
    def is_production(self) -> bool:
        return self.app_env.lower() == "production"


@lru_cache
def get_settings() -> Settings:
    return Settings()
