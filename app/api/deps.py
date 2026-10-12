from collections.abc import Iterator
from typing import Annotated
from uuid import UUID

from fastapi import Depends, Request
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
from sqlalchemy.orm import Session

from app.core.security import decode_user_id
from app.domain.exceptions import UnauthorizedError
from app.domain.rules import SchedulingRules
from app.services.appointment_service import AppointmentService
from app.services.catalog_service import CatalogService

_bearer = HTTPBearer(auto_error=False)


def get_db_session(request: Request) -> Iterator[Session]:
    session: Session = request.app.state.session_factory()
    try:
        yield session
    finally:
        session.close()


DbSession = Annotated[Session, Depends(get_db_session)]


def get_current_user_id(
    request: Request,
    credentials: Annotated[HTTPAuthorizationCredentials | None, Depends(_bearer)],
) -> UUID:
    if credentials is None:
        raise UnauthorizedError("Falta el token de autenticación")
    return decode_user_id(credentials.credentials, request.app.state.settings)


CurrentUserId = Annotated[UUID, Depends(get_current_user_id)]


def get_appointment_service(request: Request, db: DbSession) -> AppointmentService:
    settings = request.app.state.settings
    rules = SchedulingRules(
        min_hours_before_cancel_or_reschedule=settings.min_hours_before_cancel_or_reschedule,
        max_days_ahead_to_schedule=settings.max_days_ahead_to_schedule,
    )
    return AppointmentService(
        session=db,
        publisher=request.app.state.publisher,
        clock=request.app.state.clock,
        rules=rules,
    )


AppointmentServiceDep = Annotated[AppointmentService, Depends(get_appointment_service)]


def get_catalog_service(db: DbSession) -> CatalogService:
    return CatalogService(db)


CatalogServiceDep = Annotated[CatalogService, Depends(get_catalog_service)]
