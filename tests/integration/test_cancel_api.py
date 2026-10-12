import datetime as dt
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


def _owned(session: Session, user_id: uuid.UUID, **kwargs) -> Appointment:
    center = make_center(session)
    physician = make_physician(session, center)
    appointment = make_appointment(session, physician, center, user_id=user_id, **kwargs)
    session.commit()
    return appointment


def test_owner_cancels_and_publishes_snapshot_event(client, session, publisher, settings):
    appointment = _owned(session, USER_A)

    response = client.post(
        f"{BASE}/{appointment.appointment_id}/cancel", headers=auth_headers(USER_A)
    )

    assert response.status_code == 200
    assert response.json()["appointmentId"] == str(appointment.appointment_id)
    session.expire_all()
    assert session.get(Appointment, appointment.appointment_id).user_id is None

    assert len(publisher.events) == 1
    event = publisher.events[0]
    assert event.detail_type == "AppointmentCancelled"
    assert event.detail["data"]["userId"] == str(USER_A)
    assert event.detail["data"]["cancelledAt"] == "2026-10-12T15:00:00Z"
    assert event.detail["data"]["appointment"]["appointmentId"] == str(appointment.appointment_id)
    assert event.detail["data"]["appointment"]["physician"]["name"] == "Laura Gómez"


def test_non_owner_cannot_cancel(client, session, publisher, settings):
    appointment = _owned(session, USER_B)

    response = client.post(
        f"{BASE}/{appointment.appointment_id}/cancel", headers=auth_headers(USER_A)
    )

    assert response.status_code == 403
    assert response.json()["error"]["code"] == "forbidden"
    session.expire_all()
    assert session.get(Appointment, appointment.appointment_id).user_id == USER_B
    assert publisher.events == []


def test_cancel_respects_minimum_hours_in_advance(client, session, publisher, settings):
    appointment = _owned(session, USER_A, day=dt.date(2026, 10, 12), start=dt.time(12, 0))

    response = client.post(
        f"{BASE}/{appointment.appointment_id}/cancel", headers=auth_headers(USER_A)
    )

    assert response.status_code == 422
    session.expire_all()
    assert session.get(Appointment, appointment.appointment_id).user_id == USER_A
    assert publisher.events == []


def test_cancel_unknown_appointment_is_not_found(client, session, publisher, settings):
    response = client.post(f"{BASE}/{uuid.uuid4()}/cancel", headers=auth_headers(USER_A))
    assert response.status_code == 404
