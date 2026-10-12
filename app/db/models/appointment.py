import datetime as dt
import uuid

from sqlalchemy import CheckConstraint, Date, ForeignKey, Index, String, Time, Uuid
from sqlalchemy.dialects.postgresql import ENUM
from sqlalchemy.orm import Mapped, mapped_column

from app.db.base import Base
from app.domain.enums import AppointmentType
from app.domain.rules import WEEKDAY_NAMES

appointment_type_enum = ENUM(AppointmentType, name="appointment_type", create_type=False)

_WEEKDAY_SQL_LIST = ", ".join(f"'{name}'" for name in WEEKDAY_NAMES)


class Appointment(Base):
    """Cita. user_id NULO = disponible; user_id con valor = agendada por ese usuario.

    user_id no tiene FK: el id viene del claim `sub` del JWT y no hay tabla de usuarios aquí.
    """

    __tablename__ = "appointments"
    __table_args__ = (
        CheckConstraint("end_time > start_time", name="end_after_start"),
        CheckConstraint(f"weekday IN ({_WEEKDAY_SQL_LIST})", name="weekday_valid"),
        Index("ix_appointments_user_id", "user_id"),
        Index("ix_appointments_type_date_user_id", "type", "date", "user_id"),
        Index("ix_appointments_medical_center_id", "medical_center_id"),
        Index("ix_appointments_physician_id", "physician_id"),
    )

    appointment_id: Mapped[uuid.UUID] = mapped_column(Uuid, primary_key=True)
    type: Mapped[AppointmentType] = mapped_column(appointment_type_enum)
    date: Mapped[dt.date] = mapped_column(Date)
    weekday: Mapped[str] = mapped_column(String(10))
    start_time: Mapped[dt.time] = mapped_column(Time)
    end_time: Mapped[dt.time] = mapped_column(Time)
    physician_id: Mapped[uuid.UUID] = mapped_column(Uuid, ForeignKey("physicians.physician_id"))
    medical_center_id: Mapped[uuid.UUID] = mapped_column(
        Uuid, ForeignKey("medical_centers.medical_center_id")
    )
    user_id: Mapped[uuid.UUID | None] = mapped_column(Uuid, nullable=True)
