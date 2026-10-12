from datetime import date, datetime, time, timedelta

from sqlalchemy.dialects.postgresql import insert
from sqlalchemy.orm import Session

from app.db.models import Appointment
from app.domain.rules import WEEKDAY_NAMES
from seeds.seed_catalog import PHYSICIANS, center_id, physician_id, seed_id

SLOT = timedelta(minutes=30)
WORK_BLOCKS = ((time(8, 0), time(12, 0)), (time(14, 0), time(17, 0)))
CHUNK_SIZE = 500


def build_appointment_rows(start: date, days: int) -> list[dict[str, object]]:
    """Cada médico atiende un día a la semana (lunes a viernes) en bloques de 30 minutos.

    Los días alternan entre sede principal y secundaria cuando la hay. Dentro de un
    médico no hay solapamientos porque los bloques son consecutivos y disjuntos.
    """
    rows: list[dict[str, object]] = []
    for index, physician in enumerate(PHYSICIANS):
        working_weekday = index % 5
        for offset in range(days):
            day = start + timedelta(days=offset)
            if day.weekday() != working_weekday:
                continue
            week = offset // 7
            use_secondary = physician.secondary is not None and week % 2 == 1
            center_key = physician.secondary if use_secondary else physician.primary
            for block_start, block_end in WORK_BLOCKS:
                cursor = datetime.combine(day, block_start)
                limit = datetime.combine(day, block_end)
                while cursor + SLOT <= limit:
                    slot_start = cursor.time()
                    slot_end = (cursor + SLOT).time()
                    rows.append(
                        {
                            "appointment_id": seed_id(
                                "appointment",
                                f"{physician.key}:{day.isoformat()}:{slot_start.isoformat()}",
                            ),
                            "type": physician.specialty,
                            "date": day,
                            "weekday": WEEKDAY_NAMES[day.weekday()],
                            "start_time": slot_start,
                            "end_time": slot_end,
                            "physician_id": physician_id(physician.key),
                            "medical_center_id": center_id(center_key),
                            "user_id": None,
                        }
                    )
                    cursor += SLOT
    return rows


def seed_appointments(session: Session, start: date, days: int) -> int:
    """Inserta citas disponibles. No modifica citas existentes (preserva reservas)."""
    rows = build_appointment_rows(start, days)
    inserted = 0
    for offset in range(0, len(rows), CHUNK_SIZE):
        chunk = rows[offset : offset + CHUNK_SIZE]
        stmt = (
            insert(Appointment)
            .values(chunk)
            .on_conflict_do_nothing(index_elements=["appointment_id"])
            .returning(Appointment.appointment_id)
        )
        inserted += len(session.execute(stmt).all())
    return inserted
