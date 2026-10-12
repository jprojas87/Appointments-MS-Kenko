import datetime as dt
import uuid

from sqlalchemy.orm import Session

from app.db.models import Appointment
from app.domain.enums import AppointmentType
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
WEDNESDAY = dt.date(2026, 10, 21)


def _setup(session: Session):
    center = make_center(session)
    general = make_physician(session, center, AppointmentType.GENERAL)
    psychology = make_physician(session, center, AppointmentType.PSICOLOGIA)
    return center, general, psychology


def _owner(session: Session, appointment_id: uuid.UUID) -> uuid.UUID | None:
    session.expire_all()
    return session.get(Appointment, appointment_id).user_id


def test_reschedule_moves_ownership_and_publishes_event(client, session, publisher, settings):
    center, general, _ = _setup(session)
    previous = make_appointment(session, general, center, day=TUESDAY, user_id=USER_A)
    new = make_appointment(session, general, center, day=WEDNESDAY, start=dt.time(10))
    session.commit()

    response = client.post(
        f"{BASE}/{previous.appointment_id}/reschedule",
        json={"newAppointmentId": str(new.appointment_id)},
        headers=auth_headers(USER_A),
    )

    assert response.status_code == 200
    body = response.json()
    assert body["previousAppointment"]["appointmentId"] == str(previous.appointment_id)
    assert body["appointment"]["appointmentId"] == str(new.appointment_id)
    assert body["appointment"]["startTime"] == "10:00"
    assert _owner(session, previous.appointment_id) is None
    assert _owner(session, new.appointment_id) == USER_A

    assert len(publisher.events) == 1
    event = publisher.events[0]
    assert event.detail_type == "AppointmentRescheduled"
    data = event.detail["data"]
    assert set(data) == {"userId", "rescheduledAt", "previousAppointment", "appointment"}
    assert data["userId"] == str(USER_A)
    assert data["previousAppointment"]["appointmentId"] == str(previous.appointment_id)
    assert data["appointment"]["appointmentId"] == str(new.appointment_id)


def test_failed_reschedule_keeps_current_appointment(client, session, publisher, settings):
    center, general, _ = _setup(session)
    previous = make_appointment(session, general, center, day=TUESDAY, user_id=USER_A)
    taken = make_appointment(
        session, general, center, day=WEDNESDAY, start=dt.time(10), user_id=USER_B
    )
    session.commit()

    response = client.post(
        f"{BASE}/{previous.appointment_id}/reschedule",
        json={"newAppointmentId": str(taken.appointment_id)},
        headers=auth_headers(USER_A),
    )

    assert response.status_code == 409
    assert _owner(session, previous.appointment_id) == USER_A
    assert _owner(session, taken.appointment_id) == USER_B
    assert publisher.events == []


def test_reschedule_rejects_different_type(client, session, publisher, settings):
    center, general, psychology = _setup(session)
    previous = make_appointment(session, general, center, day=TUESDAY, user_id=USER_A)
    other_type = make_appointment(session, psychology, center, day=WEDNESDAY)
    session.commit()

    response = client.post(
        f"{BASE}/{previous.appointment_id}/reschedule",
        json={"newAppointmentId": str(other_type.appointment_id)},
        headers=auth_headers(USER_A),
    )

    assert response.status_code == 422
    assert _owner(session, previous.appointment_id) == USER_A
    assert _owner(session, other_type.appointment_id) is None
    assert publisher.events == []


def test_non_owner_cannot_reschedule(client, session, publisher, settings):
    center, general, _ = _setup(session)
    previous = make_appointment(session, general, center, day=TUESDAY, user_id=USER_B)
    new = make_appointment(session, general, center, day=WEDNESDAY)
    session.commit()

    response = client.post(
        f"{BASE}/{previous.appointment_id}/reschedule",
        json={"newAppointmentId": str(new.appointment_id)},
        headers=auth_headers(USER_A),
    )

    assert response.status_code == 403
    assert _owner(session, new.appointment_id) is None
    assert publisher.events == []


def test_reschedule_respects_minimum_hours_for_current(client, session, publisher, settings):
    center, general, _ = _setup(session)
    previous = make_appointment(
        session, general, center, day=dt.date(2026, 10, 12), start=dt.time(12), user_id=USER_A
    )
    new = make_appointment(session, general, center, day=WEDNESDAY)
    session.commit()

    response = client.post(
        f"{BASE}/{previous.appointment_id}/reschedule",
        json={"newAppointmentId": str(new.appointment_id)},
        headers=auth_headers(USER_A),
    )

    assert response.status_code == 422
    assert _owner(session, previous.appointment_id) == USER_A
    assert _owner(session, new.appointment_id) is None


def test_reschedule_rejects_same_appointment(client, session, publisher, settings):
    center, general, _ = _setup(session)
    previous = make_appointment(session, general, center, day=TUESDAY, user_id=USER_A)
    session.commit()

    response = client.post(
        f"{BASE}/{previous.appointment_id}/reschedule",
        json={"newAppointmentId": str(previous.appointment_id)},
        headers=auth_headers(USER_A),
    )

    assert response.status_code == 422
    assert publisher.events == []


def test_reschedule_unknown_new_appointment_keeps_current(client, session, publisher, settings):
    center, general, _ = _setup(session)
    previous = make_appointment(session, general, center, day=TUESDAY, user_id=USER_A)
    session.commit()

    response = client.post(
        f"{BASE}/{previous.appointment_id}/reschedule",
        json={"newAppointmentId": str(uuid.uuid4())},
        headers=auth_headers(USER_A),
    )

    assert response.status_code == 404
    assert _owner(session, previous.appointment_id) == USER_A
    assert publisher.events == []


def test_reschedule_requires_valid_body(client, session, publisher, settings):
    response = client.post(
        f"{BASE}/{uuid.uuid4()}/reschedule",
        json={"newAppointmentId": "no-es-uuid"},
        headers=auth_headers(USER_A),
    )
    assert response.status_code == 422
