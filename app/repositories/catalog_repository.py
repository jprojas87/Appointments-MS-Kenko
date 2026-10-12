import uuid

from sqlalchemy import or_, select
from sqlalchemy.orm import Session

from app.db.models import MedicalCenter, Physician
from app.domain.enums import AppointmentType


class CatalogRepository:
    def __init__(self, session: Session) -> None:
        self._session = session

    def list_medical_centers(self) -> list[MedicalCenter]:
        stmt = select(MedicalCenter).order_by(MedicalCenter.name)
        return list(self._session.scalars(stmt))

    def get_physician(self, physician_id: uuid.UUID) -> Physician | None:
        return self._session.get(Physician, physician_id)

    def list_physicians(
        self,
        specialty: AppointmentType | None = None,
        medical_center_id: uuid.UUID | None = None,
    ) -> list[Physician]:
        stmt = select(Physician).order_by(Physician.last_name, Physician.first_name)
        if specialty is not None:
            stmt = stmt.where(Physician.specialty == specialty)
        if medical_center_id is not None:
            stmt = stmt.where(
                or_(
                    Physician.primary_med_center_id == medical_center_id,
                    Physician.secondary_med_center_id == medical_center_id,
                )
            )
        return list(self._session.scalars(stmt))
