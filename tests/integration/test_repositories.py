import uuid
from datetime import date, time

import pytest
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from app.db.models import Appointment, MedicalCenter, Physician
from app.domain.enums import AppointmentType
from app.repositories.appointment_repository import AppointmentRepository
from app.repositories.catalog_repository import CatalogRepository

OWNER = uuid.UUID("0192b3c4-7d8e-7f10-a2b3-4c5d6e7f8000")
OTHER = uuid.UUID("0192b3c4-7d8e-7f10-a2b3-4c5d6e7f8001")


def _center(session: Session, name: str = "Centro Norte") -> MedicalCenter:
    center = MedicalCenter(medical_center_id=uuid.uuid4(), name=name, location="Bogotá")
    session.add(center)
    session.flush()
    return center


def _physician(
    session: Session,
    center: MedicalCenter,
    specialty: AppointmentType = AppointmentType.GENERAL,
    secondary: MedicalCenter | None = None,
) -> Physician:
    physician = Physician(
        physician_id=uuid.uuid4(),
        first_name="Ana",
        last_name="Pérez",
        specialty=specialty,
        primary_med_center_id=center.medical_center_id,
        secondary_med_center_id=secondary.medical_center_id if secondary else None,
    )
    session.add(physician)
    session.flush()
    return physician


def _appointment(
    session: Session,
    physician: Physician,
    center: MedicalCenter,
    *,
    start: time = time(9, 0),
    user_id: uuid.UUID | None = None,
) -> Appointment:
    appointment = Appointment(
        appointment_id=uuid.uuid4(),
        type=physician.specialty,
        date=date(2026, 10, 20),
        weekday="Tuesday",
        start_time=start,
        end_time=time(start.hour, start.minute + 30),
        physician_id=physician.physician_id,
        medical_center_id=center.medical_center_id,
        user_id=user_id,
    )
    session.add(appointment)
    session.flush()
    return appointment


def test_claim_succeeds_only_once(session: Session) -> None:
    center = _center(session)
    physician = _physician(session, center)
    appointment = _appointment(session, physician, center)
    repo = AppointmentRepository(session)

    assert repo.claim(appointment.appointment_id, OWNER) is True
    assert repo.claim(appointment.appointment_id, OTHER) is False

    session.commit()
    session.expire_all()
    assert repo.get(appointment.appointment_id).user_id == OWNER


def test_release_only_by_owner(session: Session) -> None:
    center = _center(session)
    physician = _physician(session, center)
    appointment = _appointment(session, physician, center, user_id=OWNER)
    repo = AppointmentRepository(session)

    assert repo.release(appointment.appointment_id, OTHER) is False
    assert repo.release(appointment.appointment_id, OWNER) is True

    session.commit()
    session.expire_all()
    assert repo.get(appointment.appointment_id).user_id is None


def test_get_many_for_update_returns_rows_in_id_order(session: Session) -> None:
    center = _center(session)
    physician = _physician(session, center)
    first = _appointment(session, physician, center, start=time(9, 0))
    second = _appointment(session, physician, center, start=time(10, 0))
    ids = [first.appointment_id, second.appointment_id]

    rows = AppointmentRepository(session).get_many_for_update(list(reversed(ids)))

    assert [row.appointment_id for row in rows] == sorted(ids)


def test_end_time_must_be_after_start_time(session: Session) -> None:
    center = _center(session)
    physician = _physician(session, center)
    broken = Appointment(
        appointment_id=uuid.uuid4(),
        type=AppointmentType.GENERAL,
        date=date(2026, 10, 20),
        weekday="Tuesday",
        start_time=time(10, 0),
        end_time=time(9, 30),
        physician_id=physician.physician_id,
        medical_center_id=center.medical_center_id,
    )
    session.add(broken)

    with pytest.raises(IntegrityError):
        session.flush()


def test_weekday_must_be_a_valid_name(session: Session) -> None:
    center = _center(session)
    physician = _physician(session, center)
    broken = Appointment(
        appointment_id=uuid.uuid4(),
        type=AppointmentType.GENERAL,
        date=date(2026, 10, 20),
        weekday="Martes",
        start_time=time(9, 0),
        end_time=time(9, 30),
        physician_id=physician.physician_id,
        medical_center_id=center.medical_center_id,
    )
    session.add(broken)

    with pytest.raises(IntegrityError):
        session.flush()


def test_list_physicians_filters_by_specialty_and_center(session: Session) -> None:
    norte = _center(session, "Norte")
    sur = _center(session, "Sur")
    _physician(session, norte, AppointmentType.GENERAL)
    _physician(session, norte, AppointmentType.PSICOLOGIA, secondary=sur)
    _physician(session, sur, AppointmentType.ODONTOLOGIA)
    repo = CatalogRepository(session)

    assert len(repo.list_physicians()) == 3
    assert [p.specialty for p in repo.list_physicians(specialty=AppointmentType.PSICOLOGIA)] == [
        AppointmentType.PSICOLOGIA
    ]
    # Un médico cuenta en una sede si es la principal o la secundaria.
    assert len(repo.list_physicians(medical_center_id=sur.medical_center_id)) == 2


def test_list_medical_centers_ordered_by_name(session: Session) -> None:
    _center(session, "Zeta")
    _center(session, "Alfa")

    names = [center.name for center in CatalogRepository(session).list_medical_centers()]

    assert names == ["Alfa", "Zeta"]
