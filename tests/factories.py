import datetime as dt
import time
import uuid

import jwt
from fastapi.testclient import TestClient
from sqlalchemy.orm import Session

from app.config import Settings
from app.db.models import Appointment, MedicalCenter, Physician
from app.domain.enums import AppointmentType
from app.domain.rules import BUSINESS_TIMEZONE, WEEKDAY_NAMES
from app.events.publisher import EventPublisher
from app.main import create_app

FIXED_NOW = dt.datetime(2026, 10, 12, 10, 0, tzinfo=BUSINESS_TIMEZONE)
TUESDAY = dt.date(2026, 10, 20)
JWT_SECRET = "test-secret-for-integration-tests"

USER_A = uuid.UUID("0192b3c4-7d8e-7f10-a2b3-4c5d6e7f8000")
USER_B = uuid.UUID("0192b3c4-7d8e-7f10-a2b3-4c5d6e7f8001")
USER_C = uuid.UUID("0192b3c4-7d8e-7f10-a2b3-4c5d6e7f8002")


def make_center(
    session: Session,
    name: str = "Centro Norte",
    location: str = "Calle 100 # 15-20, Bogotá",
) -> MedicalCenter:
    center = MedicalCenter(medical_center_id=uuid.uuid4(), name=name, location=location)
    session.add(center)
    session.flush()
    return center


def make_physician(
    session: Session,
    center: MedicalCenter,
    specialty: AppointmentType = AppointmentType.GENERAL,
    secondary: MedicalCenter | None = None,
) -> Physician:
    physician = Physician(
        physician_id=uuid.uuid4(),
        first_name="Laura",
        last_name="Gómez",
        specialty=specialty,
        primary_med_center_id=center.medical_center_id,
        secondary_med_center_id=secondary.medical_center_id if secondary else None,
    )
    session.add(physician)
    session.flush()
    return physician


def make_appointment(
    session: Session,
    physician: Physician,
    center: MedicalCenter,
    *,
    day: dt.date = TUESDAY,
    start: dt.time = dt.time(9, 0),
    user_id: uuid.UUID | None = None,
) -> Appointment:
    end = (dt.datetime.combine(day, start) + dt.timedelta(minutes=30)).time()
    appointment = Appointment(
        appointment_id=uuid.uuid4(),
        type=physician.specialty,
        date=day,
        weekday=WEEKDAY_NAMES[day.weekday()],
        start_time=start,
        end_time=end,
        physician_id=physician.physician_id,
        medical_center_id=center.medical_center_id,
        user_id=user_id,
    )
    session.add(appointment)
    session.flush()
    return appointment


def make_token(user_id: uuid.UUID, secret: str = JWT_SECRET, expires_in: int = 3600) -> str:
    payload = {"sub": str(user_id), "exp": int(time.time()) + expires_in}
    return jwt.encode(payload, secret, algorithm="HS256")


def auth_headers(user_id: uuid.UUID, secret: str = JWT_SECRET) -> dict[str, str]:
    return {"Authorization": f"Bearer {make_token(user_id, secret)}"}


def client_for(settings: Settings, publisher: EventPublisher) -> TestClient:
    """Cliente con reloj fijo en FIXED_NOW. Usar como context manager para ejecutar lifespan."""
    app = create_app(settings, publisher=publisher, clock=lambda: FIXED_NOW)
    return TestClient(app)
