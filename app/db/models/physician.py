import uuid

from sqlalchemy import ForeignKey, String, Uuid
from sqlalchemy.orm import Mapped, mapped_column

from app.db.base import Base
from app.db.models.appointment import appointment_type_enum
from app.domain.enums import AppointmentType


class Physician(Base):
    __tablename__ = "physicians"

    physician_id: Mapped[uuid.UUID] = mapped_column(Uuid, primary_key=True)
    first_name: Mapped[str] = mapped_column(String(100))
    last_name: Mapped[str] = mapped_column(String(100))
    specialty: Mapped[AppointmentType] = mapped_column(appointment_type_enum)
    primary_med_center_id: Mapped[uuid.UUID] = mapped_column(
        Uuid, ForeignKey("medical_centers.medical_center_id")
    )
    secondary_med_center_id: Mapped[uuid.UUID | None] = mapped_column(
        Uuid, ForeignKey("medical_centers.medical_center_id"), nullable=True
    )
