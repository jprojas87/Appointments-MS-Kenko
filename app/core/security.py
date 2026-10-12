from uuid import UUID

import jwt

from app.config import Settings
from app.domain.exceptions import UnauthorizedError


def _verification_key(settings: Settings) -> str:
    if settings.jwt_algorithm == "RS256":
        assert settings.jwt_public_key is not None
        return settings.jwt_public_key
    assert settings.jwt_secret is not None
    return settings.jwt_secret.get_secret_value()


def decode_user_id(token: str, settings: Settings) -> UUID:
    """Valida el JWT emitido por Authentication y devuelve el userId (claim sub).

    TODO: confirmar con Authentication si el emisor (iss) y la audiencia (aud) son
    obligatorios. Solo se validan si están configurados por entorno.
    """
    try:
        payload = jwt.decode(
            token,
            _verification_key(settings),
            algorithms=[settings.jwt_algorithm],
            issuer=settings.jwt_issuer,
            audience=settings.jwt_audience,
            options={
                "require": ["sub"],
                "verify_aud": settings.jwt_audience is not None,
            },
        )
    except jwt.PyJWTError as exc:
        raise UnauthorizedError("Token inválido o expirado") from exc

    try:
        return UUID(str(payload["sub"]))
    except ValueError as exc:
        raise UnauthorizedError("El claim sub no es un UUID válido") from exc
