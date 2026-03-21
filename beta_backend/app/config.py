from functools import lru_cache
from pathlib import Path
from typing import List

from pydantic import AliasChoices, Field
from pydantic import field_validator
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", env_file_encoding="utf-8", extra="ignore", populate_by_name=True)

    app_name: str = "Catch Your Partner API"
    environment: str = "development"
    debug: bool = True
    secret_key: str = Field(default="dev-secret-change-me", validation_alias=AliasChoices("SECRET_KEY", "JWT_SECRET"))
    jwt_algorithm: str = "HS256"
    jwt_expire_minutes: int = 120
    database_url: str = Field(
        default="postgresql+psycopg://postgres:postgres@db:5432/catchyourpartner",
        validation_alias=AliasChoices("DATABASE_URL", "POSTGRES_URL"),
    )
    cors_origins_raw: str = Field(
        default="http://localhost:3000,http://127.0.0.1:3000,http://localhost:8000",
        validation_alias=AliasChoices("CORS_ORIGINS_RAW", "CORS_ALLOW"),
    )
    rate_limit_enabled: bool = True
    rate_limit_per_minute: int = Field(default=120, validation_alias=AliasChoices("RATE_LIMIT_PER_MINUTE", "RATE_LIMIT"))
    auth_rate_limit_per_minute: int = 20
    radar_ttl_minutes: int = 60
    chat_expiry_hours: int = 48
    chat_message_limit: int = 20
    checkin_radius_meters: int = 250
    auto_create_tables: bool = False
    log_level: str = "INFO"
    default_admin_email: str = "admin@example.com"
    sms_provider: str = "none"
    sms_from_number: str = ""
    twilio_account_sid: str = ""
    twilio_auth_token: str = ""
    phone_verification_request_limit: int = 3
    phone_verification_request_window_minutes: int = 15
    phone_verification_lock_minutes: int = 15
    profile_photo_upload_dir: str = "beta_backend/storage/profile_photos"
    profile_photo_max_bytes: int = 5_000_000

    feature_core_enabled: bool = True
    feature_identity_enabled: bool = False
    feature_companion_enabled: bool = False
    feature_mind_enabled: bool = False
    feature_astro_enabled: bool = False

    @field_validator("debug", mode="before")
    @classmethod
    def parse_debug(cls, value):
        if isinstance(value, bool):
            return value
        if isinstance(value, str):
            lowered = value.strip().lower()
            if lowered in {"1", "true", "yes", "on", "debug"}:
                return True
            if lowered in {"0", "false", "no", "off", "release", "prod", "production"}:
                return False
        return bool(value)

    @property
    def cors_origins(self) -> List[str]:
        return [item.strip() for item in self.cors_origins_raw.split(",") if item.strip()]

    @property
    def profile_photo_upload_path(self) -> Path:
        return Path(self.profile_photo_upload_dir)


@lru_cache
def get_settings() -> Settings:
    return Settings()
