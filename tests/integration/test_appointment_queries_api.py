import datetime as dt

from sqlalchemy.orm import Session

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
TODAY = dt.date(2026, 10, 12)
TUESDAY = dt.date(2026, 10, 20)


def _setup(session: Session):
    center = make_center(session)
    physician = make_physician(session, center)
    return center, physician


def test_available_returns_only_free_future_within_window(client, session: Session, settings):
    center, physician = _setup(session)
    make_appointment(session, physician, center, day=TUESDAY, start=dt.time(9))
    make_appointment(session, physician, center, day=TUESDAY, start=dt.time(11))
    make_appointment(session, physician, center, day=TUESDAY, start=dt.time(14), user_id=USER_B)
    make_appointment(session, physician, center, day=dt.date(2026, 10, 5), start=dt.time(9))
    make_appointment(session, physician, center, day=dt.date(2027, 1, 30), start=dt.time(9))
    session.commit()

    response = client.get(f"{BASE}/available", headers=auth_headers(USER_A))

    assert response.status_code == 200
    body = response.json()
    assert body["total"] == 2
    assert [item["startTime"] for item in body["items"]] == ["09:00", "11:00"]


def test_available_excludes_slots_of_today_that_already_started(client, session: Session, settings):
    center, physician = _setup(session)
    make_appointment(session, physician, center, day=TODAY, start=dt.time(9))
    make_appointment(session, physician, center, day=TODAY, start=dt.time(11))
    session.commit()

    body = client.get(f"{BASE}/available", headers=auth_headers(USER_A)).json()

    assert body["total"] == 1
    assert body["items"][0]["startTime"] == "11:00"


def test_available_filters_by_type_center_physician_and_dates(client, session: Session, settings):
    norte = make_center(session, "Norte")
    sur = make_center(session, "Sur")
    general = make_physician(session, norte, AppointmentType.GENERAL)
    odonto = make_physician(session, sur, AppointmentType.ODONTOLOGIA)
    make_appointment(session, general, norte, day=TUESDAY, start=dt.time(9))
    make_appointment(session, odonto, sur, day=TUESDAY, start=dt.time(10))
    make_appointment(session, odonto, sur, day=TUESDAY + dt.timedelta(days=3), start=dt.time(10))
    session.commit()
    headers = auth_headers(USER_A)

    by_type = client.get(f"{BASE}/available", params={"type": "ODONTOLOGIA"}, headers=headers)
    by_center = client.get(
        f"{BASE}/available",
        params={"medical_center_id": str(norte.medical_center_id)},
        headers=headers,
    )
    by_physician = client.get(
        f"{BASE}/available",
        params={"physician_id": str(odonto.physician_id)},
        headers=headers,
    )
    by_dates = client.get(
        f"{BASE}/available",
        params={"date_from": "2026-10-21", "date_to": "2026-10-25"},
        headers=headers,
    )

    assert by_type.json()["total"] == 2
    assert by_center.json()["total"] == 1
    assert by_physician.json()["total"] == 2
    assert by_dates.json()["total"] == 1


def test_available_is_paginated_and_ordered(client, session: Session, settings):
    center, physician = _setup(session)
    for hour in (9, 10, 11, 14, 15):
        make_appointment(session, physician, center, day=TUESDAY, start=dt.time(hour))
    session.commit()
    headers = auth_headers(USER_A)

    first = client.get(f"{BASE}/available", params={"page_size": 2}, headers=headers).json()
    last = client.get(
        f"{BASE}/available", params={"page": 3, "page_size": 2}, headers=headers
    ).json()

    assert first["total"] == 5
    assert first["page"] == 1
    assert first["pageSize"] == 2
    assert [i["startTime"] for i in first["items"]] == ["09:00", "10:00"]
    assert [i["startTime"] for i in last["items"]] == ["15:00"]


def test_invalid_pagination_and_date_range_are_rejected(client, session: Session, settings):
    headers = auth_headers(USER_A)

    too_big = client.get(f"{BASE}/available", params={"page_size": 101}, headers=headers)
    reversed_dates = client.get(
        f"{BASE}/available",
        params={"date_from": "2026-10-25", "date_to": "2026-10-20"},
        headers=headers,
    )

    assert too_big.status_code == 422
    assert reversed_dates.status_code == 422
    assert reversed_dates.json()["error"]["code"] == "validation_error"


def test_me_lists_only_own_upcoming_appointments_by_default(client, session: Session, settings):
    center, physician = _setup(session)
    make_appointment(session, physician, center, day=TUESDAY, start=dt.time(9), user_id=USER_A)
    make_appointment(session, physician, center, day=dt.date(2026, 10, 5), user_id=USER_A)
    make_appointment(session, physician, center, day=TUESDAY, start=dt.time(10), user_id=USER_B)
    session.commit()
    headers = auth_headers(USER_A)

    upcoming = client.get(f"{BASE}/me", headers=headers).json()
    everything = client.get(f"{BASE}/me", params={"include_past": "true"}, headers=headers).json()

    assert upcoming["total"] == 1
    assert upcoming["items"][0]["startTime"] == "09:00"
    assert everything["total"] == 2


def test_me_requires_token(client, settings):
    response = client.get(f"{BASE}/me")
    assert response.status_code == 401
