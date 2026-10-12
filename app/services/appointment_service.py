import datetime as dt
import logging
import uuid
from collections.abc import Callable, Iterator
from contextlib import contextmanager
from dataclasses import dataclass
from typing import TypeVar

from sqlalchemy.orm import Session

from app.domain.enums import AppointmentType
from app.domain.exceptions import (
    BusinessRuleError,
    ConflictError,
    ForbiddenError,
    NotFoundError,
)
from app.domain.rules import (
    BUSINESS_TIMEZONE,
    SchedulingRules,
    ensure_modifiable,
    ensure_schedulable,
)
from app.events.envelope import EventEnvelope
from app.events.published.appointment_events import (
    appointment_cancelled,
    appointment_rescheduled,
    appointment_scheduled,
)
from app.events.publisher import EventPublisher, publish_with_retry
from app.repositories.appointment_repository import AppointmentRecord, AppointmentRepository

T = TypeVar("T")
logger = logging.getLogger(__name__)


@dataclass(frozen=True)
class PageResult[T]:
    items: list[T]
    page: int
    page_size: int
    total: int


class AppointmentService:
    """Reglas de citas. Cada operación de escritura es una transacción; el evento se publica
    solo después de confirmarla.
    """

    def __init__(
        self,
        session: Session,
        publisher: EventPublisher,
        clock: Callable[[], dt.datetime],
        rules: SchedulingRules,
    ) -> None:
        self._session = session
        self._appointments = AppointmentRepository(session)
        self._publisher = publisher
        self._clock = clock
        self._rules = rules

    def search_available(
        self,
        *,
        appointment_type: AppointmentType | None,
        medical_center_id: uuid.UUID | None,
        physician_id: uuid.UUID | None,
        date_from: dt.date | None,
        date_to: dt.date | None,
        page: int,
        page_size: int,
    ) -> PageResult[AppointmentRecord]:
        now = self._now()
        last_day = now.date() + dt.timedelta(days=self._rules.max_days_ahead_to_schedule)
        items, total = self._appointments.search_available(
            now=now,
            last_day=last_day,
            appointment_type=appointment_type,
            medical_center_id=medical_center_id,
            physician_id=physician_id,
            date_from=date_from,
            date_to=date_to,
            page=page,
            page_size=page_size,
        )
        return PageResult(items=items, page=page, page_size=page_size, total=total)

    def list_mine(
        self, user_id: uuid.UUID, *, include_past: bool, page: int, page_size: int
    ) -> PageResult[AppointmentRecord]:
        items, total = self._appointments.list_for_user(
            user_id,
            now=self._now(),
            include_past=include_past,
            page=page,
            page_size=page_size,
        )
        return PageResult(items=items, page=page, page_size=page_size, total=total)

    def schedule(self, user_id: uuid.UUID, appointment_id: uuid.UUID) -> AppointmentRecord:
        now = self._now()
        with self._unit_of_work():
            current = self._appointments.get(appointment_id)
            if current is None:
                raise NotFoundError("Cita no encontrada")
            ensure_schedulable(current.date, current.start_time, now, self._rules)
            if not self._appointments.claim(appointment_id, user_id):
                raise ConflictError("La cita no está disponible")
            record = self._details_or_fail(appointment_id)

        logger.info(
            "appointment_scheduled",
            extra={"userId": str(user_id), "appointmentId": str(appointment_id)},
        )
        self._publish(appointment_scheduled(user_id, now, record))
        return record

    def cancel(self, user_id: uuid.UUID, appointment_id: uuid.UUID) -> AppointmentRecord:
        now = self._now()
        with self._unit_of_work():
            locked = self._appointments.get_many_for_update([appointment_id])
            if not locked:
                raise NotFoundError("Cita no encontrada")
            appointment = locked[0]
            if appointment.user_id != user_id:
                raise ForbiddenError("La cita no pertenece al usuario autenticado")
            ensure_modifiable(appointment.date, appointment.start_time, now, self._rules)
            record = self._details_or_fail(appointment_id)
            if not self._appointments.release(appointment_id, user_id):
                raise ConflictError("La cita no pudo liberarse")

        logger.info(
            "appointment_cancelled",
            extra={"userId": str(user_id), "appointmentId": str(appointment_id)},
        )
        self._publish(appointment_cancelled(user_id, now, record))
        return record

    def reschedule(
        self,
        user_id: uuid.UUID,
        previous_id: uuid.UUID,
        new_id: uuid.UUID,
    ) -> tuple[AppointmentRecord, AppointmentRecord]:
        if previous_id == new_id:
            raise BusinessRuleError("La nueva cita debe ser distinta de la actual")
        now = self._now()
        with self._unit_of_work():
            locked = {
                row.appointment_id: row
                for row in self._appointments.get_many_for_update([previous_id, new_id])
            }
            previous = locked.get(previous_id)
            new = locked.get(new_id)
            if previous is None or new is None:
                raise NotFoundError("Cita no encontrada")
            if previous.user_id != user_id:
                raise ForbiddenError("La cita no pertenece al usuario autenticado")
            ensure_modifiable(previous.date, previous.start_time, now, self._rules)
            if new.type != previous.type:
                raise BusinessRuleError("La nueva cita debe ser del mismo tipo que la actual")
            ensure_schedulable(new.date, new.start_time, now, self._rules)
            if new.user_id is not None:
                raise ConflictError("La nueva cita no está disponible")

            previous_record = self._details_or_fail(previous_id)
            if not self._appointments.release(previous_id, user_id):
                raise ConflictError("La cita actual no pudo liberarse")
            if not self._appointments.claim(new_id, user_id):
                raise ConflictError("La nueva cita no está disponible")
            current_record = self._details_or_fail(new_id)

        logger.info(
            "appointment_rescheduled",
            extra={
                "userId": str(user_id),
                "previousAppointmentId": str(previous_id),
                "appointmentId": str(new_id),
            },
        )
        self._publish(appointment_rescheduled(user_id, now, previous_record, current_record))
        return previous_record, current_record

    def _now(self) -> dt.datetime:
        return self._clock().astimezone(BUSINESS_TIMEZONE)

    def _details_or_fail(self, appointment_id: uuid.UUID) -> AppointmentRecord:
        record = self._appointments.get_details(appointment_id)
        if record is None:
            raise NotFoundError("Cita no encontrada")
        return record

    def _publish(self, event: EventEnvelope) -> None:
        publish_with_retry(self._publisher, event)

    @contextmanager
    def _unit_of_work(self) -> Iterator[None]:
        try:
            yield
            self._session.commit()
        except Exception:
            self._session.rollback()
            raise
