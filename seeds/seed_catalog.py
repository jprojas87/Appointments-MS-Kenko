import uuid
from dataclasses import dataclass

from sqlalchemy.dialects.postgresql import insert
from sqlalchemy.orm import Session

from app.db.models import MedicalCenter, Physician
from app.domain.enums import AppointmentType

SEED_NAMESPACE = uuid.uuid5(uuid.NAMESPACE_URL, "https://kenko.example/seeds/appointments-service")


@dataclass(frozen=True)
class CenterSeed:
    key: str
    name: str
    location: str


@dataclass(frozen=True)
class PhysicianSeed:
    key: str
    first_name: str
    last_name: str
    specialty: AppointmentType
    primary: str
    secondary: str | None = None


CENTERS: tuple[CenterSeed, ...] = (
    CenterSeed("bogota-norte", "Centro Médico Norte", "Calle 100 # 15-20, Bogotá"),
    CenterSeed("medellin-poblado", "Centro Médico El Poblado", "Carrera 43A # 7-50, Medellín"),
    CenterSeed("cali-sur", "Centro Médico Sur", "Avenida 6N # 28-40, Cali"),
    CenterSeed(
        "barranquilla-alto-prado",
        "Centro Médico Alto Prado",
        "Carrera 53 # 76-30, Barranquilla",
    ),
    CenterSeed("bucaramanga-cabecera", "Centro Médico Cabecera", "Carrera 33 # 48-15, Bucaramanga"),
)

PHYSICIANS: tuple[PhysicianSeed, ...] = (
    PhysicianSeed("laura-gomez", "Laura", "Gómez", AppointmentType.ODONTOLOGIA, "bogota-norte"),
    PhysicianSeed(
        "andres-ruiz", "Andrés", "Ruiz", AppointmentType.GENERAL, "medellin-poblado", "cali-sur"
    ),
    PhysicianSeed("camila-torres", "Camila", "Torres", AppointmentType.PSICOLOGIA, "cali-sur"),
    PhysicianSeed(
        "mateo-herrera",
        "Mateo",
        "Herrera",
        AppointmentType.GENERAL,
        "barranquilla-alto-prado",
        "bogota-norte",
    ),
    PhysicianSeed(
        "sofia-martinez",
        "Sofía",
        "Martínez",
        AppointmentType.PSICOLOGIA,
        "bogota-norte",
        "medellin-poblado",
    ),
    PhysicianSeed(
        "daniel-vargas", "Daniel", "Vargas", AppointmentType.ODONTOLOGIA, "medellin-poblado"
    ),
    PhysicianSeed(
        "valentina-rojas",
        "Valentina",
        "Rojas",
        AppointmentType.GENERAL,
        "bucaramanga-cabecera",
    ),
    PhysicianSeed(
        "julian-castro",
        "Julián",
        "Castro",
        AppointmentType.ODONTOLOGIA,
        "cali-sur",
        "barranquilla-alto-prado",
    ),
    PhysicianSeed(
        "isabella-mora", "Isabella", "Mora", AppointmentType.PSICOLOGIA, "barranquilla-alto-prado"
    ),
    PhysicianSeed(
        "santiago-ospina",
        "Santiago",
        "Ospina",
        AppointmentType.GENERAL,
        "bogota-norte",
        "bucaramanga-cabecera",
    ),
)


def seed_id(kind: str, key: str) -> uuid.UUID:
    return uuid.uuid5(SEED_NAMESPACE, f"{kind}:{key}")


def center_id(key: str) -> uuid.UUID:
    return seed_id("medical_center", key)


def physician_id(key: str) -> uuid.UUID:
    return seed_id("physician", key)


def seed_catalog(session: Session) -> None:
    center_rows = [
        {
            "medical_center_id": center_id(center.key),
            "name": center.name,
            "location": center.location,
        }
        for center in CENTERS
    ]
    center_stmt = insert(MedicalCenter).values(center_rows)
    session.execute(
        center_stmt.on_conflict_do_update(
            index_elements=["medical_center_id"],
            set_={"name": center_stmt.excluded.name, "location": center_stmt.excluded.location},
        )
    )

    physician_rows = [
        {
            "physician_id": physician_id(physician.key),
            "first_name": physician.first_name,
            "last_name": physician.last_name,
            "specialty": physician.specialty,
            "primary_med_center_id": center_id(physician.primary),
            "secondary_med_center_id": center_id(physician.secondary)
            if physician.secondary
            else None,
        }
        for physician in PHYSICIANS
    ]
    physician_stmt = insert(Physician).values(physician_rows)
    session.execute(
        physician_stmt.on_conflict_do_update(
            index_elements=["physician_id"],
            set_={
                "first_name": physician_stmt.excluded.first_name,
                "last_name": physician_stmt.excluded.last_name,
                "specialty": physician_stmt.excluded.specialty,
                "primary_med_center_id": physician_stmt.excluded.primary_med_center_id,
                "secondary_med_center_id": physician_stmt.excluded.secondary_med_center_id,
            },
        )
    )
