import pytest
from pydantic import ValidationError

from app.config import Settings

DB_URL = "postgresql+psycopg://user:pass@localhost:5432/appointments"


def test_hs256_requires_secret() -> None:
    with pytest.raises(ValidationError):
        Settings(
            _env_file=None,
            database_url=DB_URL,
            jwt_algorithm="HS256",
            jwt_secret="",
        )


def test_rs256_requires_public_key() -> None:
    with pytest.raises(ValidationError):
        Settings(
            _env_file=None,
            database_url=DB_URL,
            jwt_algorithm="RS256",
            jwt_public_key="  ",
        )


def test_blank_optional_values_become_none() -> None:
    settings = Settings(
        _env_file=None,
        database_url=DB_URL,
        jwt_secret="secret",
        jwt_issuer="",
        jwt_audience="",
    )
    assert settings.jwt_issuer is None
    assert settings.jwt_audience is None


def test_business_rule_defaults(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.delenv("MIN_HOURS_BEFORE_CANCEL_OR_RESCHEDULE", raising=False)
    monkeypatch.delenv("MAX_DAYS_AHEAD_TO_SCHEDULE", raising=False)
    settings = Settings(_env_file=None, database_url=DB_URL, jwt_secret="secret")
    assert settings.min_hours_before_cancel_or_reschedule == 24
    assert settings.max_days_ahead_to_schedule == 90
