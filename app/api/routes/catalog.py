import uuid
from typing import Annotated

from fastapi import APIRouter, Depends, Query

from app.api.deps import CatalogServiceDep, get_current_user_id
from app.api.schemas.appointment import MedicalCenterOut, PhysicianOut
from app.domain.enums import AppointmentType

router = APIRouter(
    prefix="/catalog",
    tags=["catalog"],
    dependencies=[Depends(get_current_user_id)],
)


@router.get("/medical-centers", response_model=list[MedicalCenterOut])
def list_medical_centers(service: CatalogServiceDep) -> list[MedicalCenterOut]:
    return [MedicalCenterOut.model_validate(c) for c in service.list_medical_centers()]


@router.get("/physicians", response_model=list[PhysicianOut])
def list_physicians(
    service: CatalogServiceDep,
    specialty: AppointmentType | None = None,
    medical_center_id: Annotated[uuid.UUID | None, Query()] = None,
) -> list[PhysicianOut]:
    physicians = service.list_physicians(specialty, medical_center_id)
    return [
        PhysicianOut(
            physician_id=p.physician_id,
            first_name=p.first_name,
            last_name=p.last_name,
            specialty=p.specialty,
            primary_medical_center_id=p.primary_med_center_id,
            secondary_medical_center_id=p.secondary_med_center_id,
        )
        for p in physicians
    ]


@router.get("/appointment-types", response_model=list[AppointmentType])
def list_appointment_types(service: CatalogServiceDep) -> list[AppointmentType]:
    return service.list_appointment_types()
