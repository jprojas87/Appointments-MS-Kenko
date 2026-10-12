import uuid

from sqlalchemy.orm import Session

from app.db.models import MedicalCenter, Physician
from app.domain.enums import AppointmentType
from app.repositories.catalog_repository import CatalogRepository


class CatalogService:
    def __init__(self, session: Session) -> None:
        self._catalog = CatalogRepository(session)

    def list_medical_centers(self) -> list[MedicalCenter]:
        return self._catalog.list_medical_centers()

    def list_physicians(
        self,
        specialty: AppointmentType | None,
        medical_center_id: uuid.UUID | None,
    ) -> list[Physician]:
        return self._catalog.list_physicians(
            specialty=specialty, medical_center_id=medical_center_id
        )

    def list_appointment_types(self) -> list[AppointmentType]:
        return list(AppointmentType)
