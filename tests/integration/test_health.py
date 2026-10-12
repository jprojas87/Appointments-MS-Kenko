from fastapi.testclient import TestClient

from app.config import Settings
from app.main import create_app


def test_health_ok_when_database_is_reachable() -> None:
    settings = Settings()
    with TestClient(create_app(settings)) as client:
        response = client.get("/api/v1/health")

    assert response.status_code == 200
    assert response.json() == {
        "status": "ok",
        "checks": {"process": "ok", "database": "ok"},
    }


def test_health_degraded_when_database_is_unreachable() -> None:
    settings = Settings(
        _env_file=None,
        database_url="postgresql+psycopg://user:pass@127.0.0.1:1/appointments",
        jwt_secret="secret",
    )
    with TestClient(create_app(settings)) as client:
        response = client.get("/api/v1/health")

    assert response.status_code == 503
    assert response.json()["checks"]["database"] == "error"
