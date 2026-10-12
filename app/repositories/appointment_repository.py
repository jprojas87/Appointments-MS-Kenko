import datetime as dt
import uuid
from collections.abc import Sequence
from dataclasses import dataclass
from typing import Any

from sqlalchemy import and_, func, or_, select, update
from sqlalchemy.orm import Session

from app.db.models import Appointment, MedicalCenter, Physician
from app.domain.enums import AppointmentType


@dataclass(frozen=True)
class AppointmentRecord:
    """Cita con los datos del médico y de la sede, lista para la API y los eventos."""

    appointment_id: uuid.UUID
    type: AppointmentType
    date: dt.date
    weekday: str
    start_time: dt.time
    end_time: dt.time
    physician_id: uuid.UUID
    physician_name: str
    medical_center_id: uuid.UUID
    medical_center_name: str
    medical_center_location: str
    user_id: uuid.UUID | None


def _to_record(
    appointment: Appointment, physician: Physician, center: MedicalCenter
) -> AppointmentRecord:
    return AppointmentRecord(
        appointment_id=appointment.appointment_id,
        type=appointment.type,
        date=appointment.date,
        weekday=appointment.weekday,
        start_time=appointment.start_time,
        end_time=appointment.end_time,
        physician_id=physician.physician_id,
        physician_name=f"{physician.first_name} {physician.last_name}",
        medical_center_id=center.medical_center_id,
        medical_center_name=center.name,
        medical_center_location=center.location,
        user_id=appointment.user_id,
    )


def _future(now: dt.datetime) -> Any:
    """Cita que aún no ha empezado, en hora de negocio (America/Bogota)."""
    return or_(
        Appointment.date > now.date(),
        and_(Appointment.date == now.date(), Appointment.start_time > now.time()),
    )


_DETAILS_STMT = (
    select(Appointment, Physician, MedicalCenter)
    .join(Physician, Appointment.physician_id == Physician.physician_id)
    .join(MedicalCenter, Appointment.medical_center_id == MedicalCenter.medical_center_id)
)
_ORDER = (Appointment.date, Appointment.start_time, Appointment.appointment_id)


class AppointmentRepository:
    """Acceso a datos de citas. No hace commit: la transacción la controla el service."""

    def __init__(self, session: Session) -> None:
        self._session = session

    def get(self, appointment_id: uuid.UUID) -> Appointment | None:
        return self._session.get(Appointment, appointment_id)

    def get_details(self, appointment_id: uuid.UUID) -> AppointmentRecord | None:
        stmt = _DETAILS_STMT.where(Appointment.appointment_id == appointment_id).execution_options(
            populate_existing=True
        )
        row = self._session.execute(stmt).first()
        return _to_record(*row) if row else None

    def get_many_for_update(self, appointment_ids: Sequence[uuid.UUID]) -> list[Appointment]:
        """Bloquea las filas en orden determinista (por appointment_id) para evitar deadlocks."""
        stmt = (
            select(Appointment)
            .where(Appointment.appointment_id.in_(sorted(set(appointment_ids))))
            .order_by(Appointment.appointment_id)
            .with_for_update()
        )
        return list(self._session.scalars(stmt))

    def search_available(
        self,
        *,
        now: dt.datetime,
        last_day: dt.date,
        appointment_type: AppointmentType | None,
        medical_center_id: uuid.UUID | None,
        physician_id: uuid.UUID | None,
        date_from: dt.date | None,
        date_to: dt.date | None,
        page: int,
        page_size: int,
    ) -> tuple[list[AppointmentRecord], int]:
        conditions: list[Any] = [
            Appointment.user_id.is_(None),
            _future(now),
            Appointment.date <= last_day,
        ]
        if appointment_type is not None:
            conditions.append(Appointment.type == appointment_type)
        if medical_center_id is not None:
            conditions.append(Appointment.medical_center_id == medical_center_id)
        if physician_id is not None:
            conditions.append(Appointment.physician_id == physician_id)
        if date_from is not None:
            conditions.append(Appointment.date >= date_from)
        if date_to is not None:
            conditions.append(Appointment.date <= date_to)
        return self._page(conditions, page=page, page_size=page_size)

    def list_for_user(
        self,
        user_id: uuid.UUID,
        *,
        now: dt.datetime,
        include_past: bool,
        page: int,
        page_size: int,
    ) -> tuple[list[AppointmentRecord], int]:
        conditions: list[Any] = [Appointment.user_id == user_id]
        if not include_past:
            conditions.append(_future(now))
        return self._page(conditions, page=page, page_size=page_size)

    def claim(self, appointment_id: uuid.UUID, user_id: uuid.UUID) -> bool:
        """Asigna la cita solo si está disponible. Devuelve False si ya tenía dueño."""
        stmt = (
            update(Appointment)
            .where(
                Appointment.appointment_id == appointment_id,
                Appointment.user_id.is_(None),
            )
            .values(user_id=user_id)
            .execution_options(synchronize_session=False)
        )
        result = self._session.execute(stmt)
        return result.rowcount == 1

    def release(self, appointment_id: uuid.UUID, user_id: uuid.UUID) -> bool:
        """Libera la cita solo si pertenece a user_id. Devuelve False si no es del usuario."""
        stmt = (
            update(Appointment)
            .where(
                Appointment.appointment_id == appointment_id,
                Appointment.user_id == user_id,
            )
            .values(user_id=None)
            .execution_options(synchronize_session=False)
        )
        result = self._session.execute(stmt)
        return result.rowcount == 1

    def _page(
        self, conditions: list[Any], *, page: int, page_size: int
    ) -> tuple[list[AppointmentRecord], int]:
        total = (
            self._session.scalar(select(func.count()).select_from(Appointment).where(*conditions))
            or 0
        )
        stmt = (
            _DETAILS_STMT.where(*conditions)
            .order_by(*_ORDER)
            .offset((page - 1) * page_size)
            .limit(page_size)
            .execution_options(populate_existing=True)
        )
        rows = self._session.execute(stmt).all()
        return [_to_record(*row) for row in rows], total
