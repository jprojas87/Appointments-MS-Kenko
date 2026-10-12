import uuid
from collections.abc import Sequence

from sqlalchemy import select, update
from sqlalchemy.orm import Session

from app.db.models import Appointment


class AppointmentRepository:
    """Acceso a datos de citas. No hace commit: la transacción la controla el service."""

    def __init__(self, session: Session) -> None:
        self._session = session

    def get(self, appointment_id: uuid.UUID) -> Appointment | None:
        return self._session.get(Appointment, appointment_id)

    def get_many_for_update(self, appointment_ids: Sequence[uuid.UUID]) -> list[Appointment]:
        """Bloquea las filas en orden determinista (por appointment_id) para evitar deadlocks."""
        stmt = (
            select(Appointment)
            .where(Appointment.appointment_id.in_(sorted(set(appointment_ids))))
            .order_by(Appointment.appointment_id)
            .with_for_update()
        )
        return list(self._session.scalars(stmt))

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
