"""Seeds idempotentes: python -m seeds.run

Crea centros médicos, médicos y citas disponibles de los próximos 60 días (America/Bogota).
Puede ejecutarse varias veces sin duplicar datos ni borrar reservas.
"""

import logging
from datetime import date, datetime, timedelta

from sqlalchemy.orm import sessionmaker

from app.config import get_settings
from app.core.logging import configure_logging
from app.db.session import create_db_engine, create_session_factory
from app.domain.rules import BUSINESS_TIMEZONE
from seeds.seed_appointments import seed_appointments
from seeds.seed_catalog import seed_catalog

WINDOW_DAYS = 60
logger = logging.getLogger(__name__)


def run_seeds(session_factory: sessionmaker, today: date) -> int:
    """Devuelve el número de citas nuevas insertadas. Todo ocurre en una sola transacción."""
    start = today + timedelta(days=1)
    with session_factory.begin() as session:
        seed_catalog(session)
        return seed_appointments(session, start=start, days=WINDOW_DAYS)


def main() -> None:
    settings = get_settings()
    configure_logging(settings.log_level)
    engine = create_db_engine(settings.database_url)
    try:
        today = datetime.now(BUSINESS_TIMEZONE).date()
        inserted = run_seeds(create_session_factory(engine), today=today)
    finally:
        engine.dispose()
    logger.info("seeds_completed", extra={"appointmentsInserted": inserted})


if __name__ == "__main__":
    main()
