from collections import defaultdict
from datetime import date, timedelta

from sqlalchemy import func, select
from sqlalchemy.orm import Session, sessionmaker

from app.db.models import Appointment, MedicalCenter, Physician
from app.domain.enums import AppointmentType
from seeds.run import WINDOW_DAYS, run_seeds

TODAY = date(2026, 10, 12)
FIRST_DAY = TODAY + timedelta(days=1)
LAST_DAY = TODAY + timedelta(days=WINDOW_DAYS)


def _counts(session: Session) -> tuple[int, int, int]:
    return (
        session.scalar(select(func.count()).select_from(MedicalCenter)) or 0,
        session.scalar(select(func.count()).select_from(Physician)) or 0,
        session.scalar(select(func.count()).select_from(Appointment)) or 0,
    )


def test_seeds_are_idempotent(session: Session, session_factory: sessionmaker[Session]) -> None:
    first_inserted = run_seeds(session_factory, today=TODAY)
    counts_after_first = _counts(session)

    second_inserted = run_seeds(session_factory, today=TODAY)

    assert first_inserted == counts_after_first[2] > 0
    assert second_inserted == 0
    assert _counts(session) == counts_after_first


def test_catalog_has_expected_volume_and_coverage(
    session: Session, session_factory: sessionmaker[Session]
) -> None:
    run_seeds(session_factory, today=TODAY)

    centers = session.scalars(select(MedicalCenter)).all()
    physicians = session.scalars(select(Physician)).all()

    assert 4 <= len(centers) <= 5
    assert 8 <= len(physicians) <= 12
    assert {p.specialty for p in physicians} == set(AppointmentType)
    assert any(p.secondary_med_center_id is not None for p in physicians)
    assert all(p.primary_med_center_id != p.secondary_med_center_id for p in physicians)


def test_appointments_are_valid_available_and_within_window(
    session: Session, session_factory: sessionmaker[Session]
) -> None:
    run_seeds(session_factory, today=TODAY)
    appointments = session.scalars(select(Appointment)).all()
    physicians = {p.physician_id: p for p in session.scalars(select(Physician)).all()}

    assert appointments
    for appointment in appointments:
        assert appointment.user_id is None
        assert FIRST_DAY <= appointment.date <= LAST_DAY
        assert appointment.date.weekday() < 5, "solo lunes a viernes"
        assert appointment.weekday == appointment.date.strftime("%A")
        assert appointment.type == physicians[appointment.physician_id].specialty
        duration = appointment.end_time.hour * 60 + appointment.end_time.minute
        duration -= appointment.start_time.hour * 60 + appointment.start_time.minute
        assert duration == 30, "bloques de 30 minutos"


def test_appointments_do_not_overlap_per_physician(
    session: Session, session_factory: sessionmaker[Session]
) -> None:
    run_seeds(session_factory, today=TODAY)
    by_physician: dict[object, list[tuple[date, object, object]]] = defaultdict(list)
    for appointment in session.scalars(select(Appointment)).all():
        by_physician[appointment.physician_id].append(
            (appointment.date, appointment.start_time, appointment.end_time)
        )

    for slots in by_physician.values():
        slots.sort()
        for previous, current in zip(slots, slots[1:], strict=False):
            if previous[0] == current[0]:
                assert previous[2] <= current[1], "solapamiento de citas del mismo médico"
