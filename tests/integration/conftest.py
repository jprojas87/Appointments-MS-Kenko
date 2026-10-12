from collections.abc import Iterator

import pytest
from fastapi.testclient import TestClient

from app.config import Settings
from app.events.adapters.fake_publisher import FakePublisher
from tests.factories import JWT_SECRET, client_for


@pytest.fixture
def settings(test_database_url: str) -> Settings:
    return Settings(
        _env_file=None,
        database_url=test_database_url,
        jwt_secret=JWT_SECRET,
        min_hours_before_cancel_or_reschedule=24,
        max_days_ahead_to_schedule=90,
    )


@pytest.fixture
def publisher() -> FakePublisher:
    return FakePublisher()


@pytest.fixture
def client(settings: Settings, publisher: FakePublisher) -> Iterator[TestClient]:
    with client_for(settings, publisher) as test_client:
        yield test_client
