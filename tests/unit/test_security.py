import time
import uuid

import jwt
import pytest
from cryptography.hazmat.primitives import serialization
from cryptography.hazmat.primitives.asymmetric import rsa

from app.config import Settings
from app.core.security import decode_user_id
from app.domain.exceptions import UnauthorizedError

DB_URL = "postgresql+psycopg://user:pass@localhost:5432/appointments"
SECRET = "unit-test-secret"
USER = uuid.UUID("0192b3c4-7d8e-7f10-a2b3-4c5d6e7f8000")


def _settings(**overrides: object) -> Settings:
    values: dict[str, object] = {"_env_file": None, "database_url": DB_URL, "jwt_secret": SECRET}
    values.update(overrides)
    return Settings(**values)  # type: ignore[arg-type]


def _token(claims: dict[str, object], secret: str = SECRET) -> str:
    return jwt.encode(claims, secret, algorithm="HS256")


def test_valid_token_returns_user_id() -> None:
    token = _token({"sub": str(USER), "exp": int(time.time()) + 60})
    assert decode_user_id(token, _settings()) == USER


def test_token_without_expiration_is_accepted() -> None:
    assert decode_user_id(_token({"sub": str(USER)}), _settings()) == USER


def test_expired_token_is_rejected() -> None:
    token = _token({"sub": str(USER), "exp": int(time.time()) - 10})
    with pytest.raises(UnauthorizedError):
        decode_user_id(token, _settings())


def test_wrong_signature_is_rejected() -> None:
    token = _token({"sub": str(USER)}, secret="otro-secreto")
    with pytest.raises(UnauthorizedError):
        decode_user_id(token, _settings())


def test_unsigned_token_is_rejected() -> None:
    token = jwt.encode({"sub": str(USER)}, None, algorithm="none")
    with pytest.raises(UnauthorizedError):
        decode_user_id(token, _settings())


def test_missing_sub_is_rejected() -> None:
    with pytest.raises(UnauthorizedError):
        decode_user_id(_token({"exp": int(time.time()) + 60}), _settings())


def test_sub_must_be_uuid() -> None:
    with pytest.raises(UnauthorizedError):
        decode_user_id(_token({"sub": "no-es-uuid"}), _settings())


def test_issuer_is_enforced_only_when_configured() -> None:
    settings = _settings(jwt_issuer="authentication")
    with pytest.raises(UnauthorizedError):
        decode_user_id(_token({"sub": str(USER)}), settings)
    assert decode_user_id(_token({"sub": str(USER), "iss": "authentication"}), settings) == USER


def test_rs256_uses_public_key() -> None:
    private_key = rsa.generate_private_key(public_exponent=65537, key_size=2048)
    public_pem = (
        private_key.public_key()
        .public_bytes(serialization.Encoding.PEM, serialization.PublicFormat.SubjectPublicKeyInfo)
        .decode()
    )
    private_pem = private_key.private_bytes(
        serialization.Encoding.PEM,
        serialization.PrivateFormat.PKCS8,
        serialization.NoEncryption(),
    )
    token = jwt.encode({"sub": str(USER)}, private_pem, algorithm="RS256")

    settings = _settings(jwt_algorithm="RS256", jwt_public_key=public_pem, jwt_secret=None)
    assert decode_user_id(token, settings) == USER
