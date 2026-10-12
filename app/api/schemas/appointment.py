import datetime as dt
from typing import Annotated, TypeVar
from uuid import UUID

from pydantic import BaseModel, ConfigDict, PlainSerializer
from pydantic.alias_generators import to_camel

from app.domain.enums import AppointmentType
from app.domain.rules import format_hhmm
from app.repositories.appointment_repository import AppointmentRecord

T = TypeVar("T")

HourMinute = Annotated[dt.time, PlainSerializer(format_hhmm, return_type=str)]


class CamelModel(BaseModel):
    """Entrada y salida JSON en camelCase. Los query params usan snake_case."""

    model_config = ConfigDict(alias_generator=to_camel, populate_by_name=True, from_attributes=True)


class PhysicianRef(CamelModel):
    physician_id: UUID
    name: str


class MedicalCenterRef(CamelModel):
    medical_center_id: UUID
    name: str
    location: str


class AppointmentOut(CamelModel):
    appointment_id: UUID
    type: AppointmentType
    date: dt.date
    weekday: str
    start_time: HourMinute
    end_time: HourMinute
    physician: PhysicianRef
    medical_center: MedicalCenterRef

    @classmethod
    def from_record(cls, record: AppointmentRecord) -> "AppointmentOut":
        return cls(
            appointment_id=record.appointment_id,
            type=record.type,
            date=record.date,
            weekday=record.weekday,
            start_time=record.start_time,
            end_time=record.end_time,
            physician=PhysicianRef(physician_id=record.physician_id, name=record.physician_name),
            medical_center=MedicalCenterRef(
                medical_center_id=record.medical_center_id,
                name=record.medical_center_name,
                location=record.medical_center_location,
            ),
        )


class PageOut[T](CamelModel):
    items: list[T]
    page: int
    page_size: int
    total: int


class RescheduleRequest(CamelModel):
    new_appointment_id: UUID


class RescheduleOut(CamelModel):
    previous_appointment: AppointmentOut
    appointment: AppointmentOut


class MedicalCenterOut(CamelModel):
    medical_center_id: UUID
    name: str
    location: str


class PhysicianOut(CamelModel):
    physician_id: UUID
    first_name: str
    last_name: str
    specialty: AppointmentType
    primary_medical_center_id: UUID
    secondary_medical_center_id: UUID | None
