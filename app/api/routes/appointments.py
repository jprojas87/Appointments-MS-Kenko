from typing import Annotated
from uuid import UUID

from fastapi import APIRouter, Depends, Query

from app.api.deps import AppointmentServiceDep, CurrentUserId, get_current_user_id
from app.api.schemas.appointment import AppointmentOut, PageOut, RescheduleOut, RescheduleRequest
from app.api.schemas.filters import AvailableFilters, MyAppointmentsFilters
from app.repositories.appointment_repository import AppointmentRecord
from app.services.appointment_service import PageResult

router = APIRouter(
    prefix="/appointments",
    tags=["appointments"],
    dependencies=[Depends(get_current_user_id)],
)


def _page(result: PageResult[AppointmentRecord]) -> PageOut[AppointmentOut]:
    return PageOut[AppointmentOut](
        items=[AppointmentOut.from_record(record) for record in result.items],
        page=result.page,
        page_size=result.page_size,
        total=result.total,
    )


@router.get("/available", response_model=PageOut[AppointmentOut])
def list_available(
    service: AppointmentServiceDep,
    filters: Annotated[AvailableFilters, Query()],
) -> PageOut[AppointmentOut]:
    result = service.search_available(
        appointment_type=filters.type,
        medical_center_id=filters.medical_center_id,
        physician_id=filters.physician_id,
        date_from=filters.date_from,
        date_to=filters.date_to,
        page=filters.page,
        page_size=filters.page_size,
    )
    return _page(result)


@router.get("/me", response_model=PageOut[AppointmentOut])
def list_mine(
    user_id: CurrentUserId,
    service: AppointmentServiceDep,
    filters: Annotated[MyAppointmentsFilters, Query()],
) -> PageOut[AppointmentOut]:
    result = service.list_mine(
        user_id,
        include_past=filters.include_past,
        page=filters.page,
        page_size=filters.page_size,
    )
    return _page(result)


@router.post("/{appointment_id}/schedule", response_model=AppointmentOut)
def schedule(
    appointment_id: UUID,
    user_id: CurrentUserId,
    service: AppointmentServiceDep,
) -> AppointmentOut:
    return AppointmentOut.from_record(service.schedule(user_id, appointment_id))


@router.post("/{appointment_id}/cancel", response_model=AppointmentOut)
def cancel(
    appointment_id: UUID,
    user_id: CurrentUserId,
    service: AppointmentServiceDep,
) -> AppointmentOut:
    return AppointmentOut.from_record(service.cancel(user_id, appointment_id))


@router.post("/{appointment_id}/reschedule", response_model=RescheduleOut)
def reschedule(
    appointment_id: UUID,
    body: RescheduleRequest,
    user_id: CurrentUserId,
    service: AppointmentServiceDep,
) -> RescheduleOut:
    previous, current = service.reschedule(user_id, appointment_id, body.new_appointment_id)
    return RescheduleOut(
        previous_appointment=AppointmentOut.from_record(previous),
        appointment=AppointmentOut.from_record(current),
    )
