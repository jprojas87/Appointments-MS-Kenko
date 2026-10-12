import threading
import uuid
from concurrent.futures import ThreadPoolExecutor

from sqlalchemy.orm import Session

from app.db.models import Appointment
from app.events.adapters.fake_publisher import FakePublisher
from tests.factories import auth_headers, client_for, make_appointment, make_center, make_physician

BASE = "/api/v1/appointments"
CONTENDERS = 10


def _free_appointment(session: Session):
    center = make_center(session)
    physician = make_physician(session, center)
    appointment = make_appointment(session, physician, center)
    session.commit()
    return appointment


def test_only_one_of_many_simultaneous_schedules_wins(
    client, session: Session, publisher, settings
):
    appointment = _free_appointment(session)
    users = [uuid.uuid4() for _ in range(CONTENDERS)]
    barrier = threading.Barrier(CONTENDERS)

    def attempt(user_id: uuid.UUID) -> int:
        barrier.wait()
        response = client.post(
            f"{BASE}/{appointment.appointment_id}/schedule",
            headers=auth_headers(user_id),
        )
        return response.status_code

    with ThreadPoolExecutor(max_workers=CONTENDERS) as pool:
        statuses = list(pool.map(attempt, users))

    assert sorted(statuses) == [200] + [409] * (CONTENDERS - 1)
    assert len(publisher.events) == 1
    session.expire_all()
    owner = session.get(Appointment, appointment.appointment_id).user_id
    assert owner in users


def test_transient_publish_failure_is_retried(settings, session: Session):
    appointment = _free_appointment(session)
    publisher = FakePublisher(failures=2)

    with client_for(settings, publisher) as client:
        response = client.post(
            f"{BASE}/{appointment.appointment_id}/schedule",
            headers=auth_headers(uuid.uuid4()),
        )

    assert response.status_code == 200
    assert len(publisher.events) == 1


def test_permanent_publish_failure_does_not_revert_the_booking(settings, session: Session):
    appointment = _free_appointment(session)
    owner = uuid.uuid4()
    publisher = FakePublisher(failures=100)

    with client_for(settings, publisher) as client:
        response = client.post(
            f"{BASE}/{appointment.appointment_id}/schedule",
            headers=auth_headers(owner),
        )

    assert response.status_code == 200
    assert publisher.events == []
    session.expire_all()
    assert session.get(Appointment, appointment.appointment_id).user_id == owner
