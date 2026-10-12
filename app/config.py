from functools import lru_cache
from typing import Any, Literal

from pydantic import Field, SecretStr, field_validator, model_validator
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    """Configuración del servicio. Solo variables de entorno; nunca secretos en el código."""

    model_config = SettingsConfigDict(env_file=".env", extra="ignore")

    environment: Literal["local", "dev", "prod"] = "local"
    log_level: Literal["DEBUG", "INFO", "WARNING", "ERROR"] = "INFO"

    database_url: str

    aws_region: str = "us-east-1"
    event_bus_name: str = "kenko-dev-bus"

    jwt_algorithm: Literal["HS256", "RS256"] = "HS256"
    jwt_secret: SecretStr | None = None
    jwt_public_key: str | None = None
    jwt_issuer: str | None = None
    jwt_audience: str | None = None

    min_hours_before_cancel_or_reschedule: int = Field(default=24, ge=0)
    max_days_ahead_to_schedule: int = Field(default=90, ge=1)

    @field_validator("jwt_secret", "jwt_public_key", "jwt_issuer", "jwt_audience", mode="before")
    @classmethod
    def _blank_to_none(cls, value: Any) -> Any:
        if isinstance(value, str) and not value.strip():
            return None
        return value

    @model_validator(mode="after")
    def _check_jwt_material(self) -> "Settings":
        if self.jwt_algorithm == "HS256" and self.jwt_secret is None:
            raise ValueError("JWT_SECRET es obligatorio cuando JWT_ALGORITHM=HS256")
        if self.jwt_algorithm == "RS256" and self.jwt_public_key is None:
            raise ValueError("JWT_PUBLIC_KEY es obligatorio cuando JWT_ALGORITHM=RS256")
        return self


@lru_cache
def get_settings() -> Settings:
    return Settings()
