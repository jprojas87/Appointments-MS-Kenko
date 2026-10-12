import json
import logging

from fastapi import Request
from fastapi.testclient import TestClient

from app.config import Settings
from app.core.logging import CORRELATION_HEADER, JsonFormatter, correlation_id_var
from app.domain.exceptions import NotFoundError
from app.main import create_app

DB_URL = "postgresql+psycopg://user:pass@localhost:5432/appointments"
CORRELATION_ID = "7e8f9a0b-2c3d-4e5f-9a1b-3c4d5e6f7a8b"
USER_ID = "0192b3c4-7d8e-7f10-a2b3-4c5d6e7f8000"


def _build_client() -> TestClient:
    app = create_app(Settings(_env_file=None, database_url=DB_URL, jwt_secret="secret"))

    def not_found() -> None:
        raise NotFoundError("Cita no encontrada")

    def needs_int(value: int) -> dict[str, int]:
        return {"value": value}

    def crash(request: Request) -> None:
        raise RuntimeError("boom")

    app.add_api_route("/test/not-found", not_found)
    app.add_api_route("/test/needs-int", needs_int)
    app.add_api_route("/test/crash", crash)
    return TestClient(app, raise_server_exceptions=False)


def test_json_formatter_includes_correlation_id_and_extra_fields() -> None:
    token = correlation_id_var.set(CORRELATION_ID)
    try:
        record = logging.LogRecord("test", logging.INFO, __file__, 1, "cita agendada", None, None)
        record.userId = USER_ID
        payload = json.loads(JsonFormatter().format(record))
    finally:
        correlation_id_var.reset(token)

    assert payload["message"] == "cita agendada"
    assert payload["level"] == "INFO"
    assert payload["correlationId"] == CORRELATION_ID
    assert payload["userId"] == USER_ID


def test_correlation_id_is_echoed_when_valid() -> None:
    client = _build_client()
    response = client.get("/test/not-found", headers={CORRELATION_HEADER: CORRELATION_ID})
    assert response.headers[CORRELATION_HEADER] == CORRELATION_ID


def test_correlation_id_is_generated_when_missing_or_invalid() -> None:
    client = _build_client()
    response = client.get("/test/not-found", headers={CORRELATION_HEADER: "no-es-uuid"})
    generated = response.headers[CORRELATION_HEADER]
    assert generated != "no-es-uuid"
    assert len(generated) == 36


def test_app_error_uses_uniform_format() -> None:
    client = _build_client()
    response = client.get("/test/not-found", headers={CORRELATION_HEADER: CORRELATION_ID})
    assert response.status_code == 404
    assert response.json() == {
        "error": {
            "code": "not_found",
            "message": "Cita no encontrada",
            "correlationId": CORRELATION_ID,
        }
    }


def test_validation_error_uses_uniform_format() -> None:
    client = _build_client()
    response = client.get("/test/needs-int", params={"value": "abc"})
    assert response.status_code == 422
    body = response.json()
    assert body["error"]["code"] == "validation_error"
    assert body["error"]["details"][0]["loc"] == ["query", "value"]


def test_unhandled_error_returns_500_without_leaking_details() -> None:
    client = _build_client()
    response = client.get("/test/crash")
    assert response.status_code == 500
    assert response.json()["error"]["code"] == "internal_error"
    assert "boom" not in response.text
