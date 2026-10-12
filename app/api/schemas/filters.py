import datetime as dt
from uuid import UUID

from pydantic import BaseModel, Field, model_validator

from app.domain.enums import AppointmentType


class PageParams(BaseModel):
    page: int = Field(default=1, ge=1)
    page_size: int = Field(default=20, ge=1, le=100)


class AvailableFilters(PageParams):
    type: AppointmentType | None = None
    medical_center_id: UUID | None = None
    physician_id: UUID | None = None
    date_from: dt.date | None = None
    date_to: dt.date | None = None

    @model_validator(mode="after")
    def _check_date_range(self) -> "AvailableFilters":
        if self.date_from and self.date_to and self.date_to < self.date_from:
            raise ValueError("date_to debe ser igual o posterior a date_from")
        return self


class MyAppointmentsFilters(PageParams):
    include_past: bool = False
