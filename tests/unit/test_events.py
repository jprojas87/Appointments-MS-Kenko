import datetime as dt
import uuid

import pytest

from app.core.logging import correlation_id_var
from app.domain.rules import BUSINESS_TIMEZONE
from app.events.envelope import EVENT_VERSION, SOURCE, build_event
from app.events.publisher import publish_with_retry

NOW = dt.datetime(2026, 10, 12, 10, 0, tzinfo=BUSINESS_TIMEZONE)
USER = "0192b3c4-7d8e-7f10-a2b3-4c5d6e7f8000"


def test_envelope_has_metadata_and_data() -> None:
    event = build_event("AppointmentCancelled", {"userId": USER}, occurred_at=NOW)

    assert event.source == SOURCE == "kenko.appointments"
    assert event.detail_type == "AppointmentCancelled"
    metadata = event.detail["metadata"]
    assert set(metadata) == {"eventId", "eventVersion", "occurredAt", "correlationId"}
    assert metadata["eventVersion"] == EVENT_VERSION == "1"
    assert metadata["occurredAt"] == "2026-10-12T15:00:00Z"
    assert uuid.UUID(metadata["eventId"]).version == 7
    assert event.detail["data"] == {"userId": USER}
    assert event.user_id == USER


def test_envelope_uses_request_correlation_id_when_present() -> None:
    correlation = "7e8f9a0b-2c3d-4e5f-9a1b-3c4d5e6f7a8b"
    token = correlation_id_var.set(correlation)
    try:
        event = build_event("AppointmentCancelled", {"userId": USER}, occurred_at=NOW)
    finally:
        correlation_id_var.reset(token)

    assert event.detail["metadata"]["correlationId"] == correlation


def test_envelope_generates_correlation_id_when_absent() -> None:
    event = build_event("AppointmentCancelled", {"userId": USER}, occurred_at=NOW)
    assert uuid.UUID(event.detail["metadata"]["correlationId"])


class _FlakyPublisher:
    def __init__(self, failures: int) -> None:
        self.failures = failures
        self.calls = 0

    def publish(self, event: object) -> None:
        self.calls += 1
        if self.calls <= self.failures:
            raise RuntimeError("boom")


def test_publish_retries_with_bounded_backoff_until_success() -> None:
    delays: list[float] = []
    publisher = _FlakyPublisher(failures=2)
    event = build_event("AppointmentCancelled", {"userId": USER}, occurred_at=NOW)

    delivered = publish_with_retry(publisher, event, sleep=delays.append)

    assert delivered is True
    assert publisher.calls == 3
    assert delays == [0.2, 0.4]


def test_publish_gives_up_after_attempts_and_reports_failure(
    caplog: pytest.LogCaptureFixture,
) -> None:
    delays: list[float] = []
    publisher = _FlakyPublisher(failures=10)
    event = build_event("AppointmentCancelled", {"userId": USER}, occurred_at=NOW)

    with caplog.at_level("ERROR"):
        delivered = publish_with_retry(publisher, event, attempts=3, sleep=delays.append)

    assert delivered is False
    assert publisher.calls == 3
    assert len(delays) == 2
    assert any(record.getMessage() == "event_publish_failed" for record in caplog.records)
