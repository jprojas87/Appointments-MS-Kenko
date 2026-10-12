import datetime as dt
import json
import uuid

from sqlalchemy.orm import Session

from app.db.models import Appointment
from tests.factories import (
    USER_A,
    USER_B,
    auth_headers,
    make_appointment,
    make_center,
    make_physician,
)

BASE = "/api/v1/appointments"
TUESDAY = dt.date(2026, 10, 20)


def _available(session: Session, **kwargs) -> Appointment:
    center = make_center(session)
    physician = make_physician(session, center)
    appointment = make_appointment(session, physician, center, **kwargs)
    session.commit()
    return appointment


def test_schedule_books_slot_and_publishes_one_event(client, session, publisher, settings):
    appointment = _available(session)
    correlation = "7e8f9a0b-2c3d-4e5f-9a1b-3c4d5e6f7a8b"

    response = client.post(
        f"{BASE}/{appointment.appointment_id}/schedule",
        headers={**auth_headers(USER_A), "X-Correlation-Id": correlation},
    )

    assert response.status_code == 200
    body = response.json()
    assert body["appointmentId"] == str(appointment.appointment_id)
    assert body["startTime"] == "09:00"
    assert body["physician"]["name"] == "Laura Gómez"
    assert "userId" not in body

    session.expire_all()
    assert session.get(Appointment, appointment.appointment_id).user_id == USER_A

    assert len(publisher.events) == 1
    event = publisher.events[0]
    assert event.source == "kenko.appointments"
    assert event.detail_type == "AppointmentScheduled"
    assert set(event.detail) == {"metadata", "data"}
    assert set(event.detail["metadata"]) == {
        "eventId",
        "eventVersion",
        "occurredAt",
        "correlationId",
    }
    assert event.detail["metadata"]["eventVersion"] == "1"
    assert event.detail["metadata"]["occurredAt"] == "2026-10-12T15:00:00Z"
    assert event.detail["metadata"]["correlationId"] == correlation
    assert uuid.UUID(event.detail["metadata"]["eventId"]).version == 7

    data = event.detail["data"]
    assert set(data) == {"userId", "scheduledAt", "appointment"}
    assert data["userId"] == str(USER_A)
    assert data["scheduledAt"] == "2026-10-12T15:00:00Z"
    assert set(data["appointment"]) == {
        "appointmentId",
        "type",
        "date",
        "weekday",
        "startTime",
        "endTime",
        "physician",
        "medicalCenter",
    }
    assert data["appointment"]["startTime"] == "09:00"
    assert data["appointment"]["endTime"] == "09:30"
    assert data["appointment"]["medicalCenter"]["location"] == "Calle 100 # 15-20, Bogotá"
    assert "patientId" not in json.dumps(event.detail)


def test_schedule_rejects_appointment_in_the_past(client, session, publisher, settings):
    appointment = _available(session, day=dt.date(2026, 10, 5))

    response = client.post(
        f"{BASE}/{appointment.appointment_id}/schedule", headers=auth_headers(USER_A)
    )

    assert response.status_code == 422
    assert response.json()["error"]["code"] == "business_rule_violation"
    assert publisher.events == []


def test_schedule_rejects_beyond_max_days_ahead(client, session, publisher, settings):
    appointment = _available(session, day=dt.date(2027, 1, 30))

    response = client.post(
        f"{BASE}/{appointment.appointment_id}/schedule", headers=auth_headers(USER_A)
    )

    assert response.status_code == 422
    assert publisher.events == []


def test_schedule_conflicts_when_already_taken(client, session, publisher, settings):
    appointment = _available(session, user_id=USER_B)

    response = client.post(
        f"{BASE}/{appointment.appointment_id}/schedule", headers=auth_headers(USER_A)
    )

    assert response.status_code == 409
    assert response.json()["error"]["code"] == "conflict"
    session.expire_all()
    assert session.get(Appointment, appointment.appointment_id).user_id == USER_B
    assert publisher.events == []


def test_schedule_unknown_appointment_is_not_found(client, session, publisher, settings):
    response = client.post(f"{BASE}/{uuid.uuid4()}/schedule", headers=auth_headers(USER_A))

    assert response.status_code == 404
    assert response.json()["error"]["code"] == "not_found"


def test_schedule_requires_token(client, session, publisher, settings):
    appointment = _available(session)

    response = client.post(f"{BASE}/{appointment.appointment_id}/schedule")

    assert response.status_code == 401
    assert publisher.events == []
