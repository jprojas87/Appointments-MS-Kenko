from collections.abc import Iterator
from pathlib import Path

import pytest
from alembic import command
from alembic.config import Config
from sqlalchemy import Engine, create_engine, text
from sqlalchemy.engine import make_url
from sqlalchemy.orm import Session, sessionmaker

from app.config import Settings

ROOT = Path(__file__).resolve().parents[1]
TEST_DB_NAME = "appointments_test"


def _alembic_config(database_url: str) -> Config:
    config = Config(str(ROOT / "alembic.ini"))
    config.set_main_option("script_location", str(ROOT / "migrations"))
    config.attributes["database_url"] = database_url
    return config


@pytest.fixture(scope="session")
def test_database_url() -> str:
    """Crea una base aparte (appointments_test) para no tocar los datos de desarrollo."""
    base_url = make_url(Settings().database_url)
    admin_engine = create_engine(base_url.set(database="postgres"), isolation_level="AUTOCOMMIT")
    with admin_engine.connect() as connection:
        exists = connection.execute(
            text("SELECT 1 FROM pg_database WHERE datname = :name"), {"name": TEST_DB_NAME}
        ).scalar()
        if not exists:
            connection.execute(text(f'CREATE DATABASE "{TEST_DB_NAME}"'))
    admin_engine.dispose()

    url = base_url.set(database=TEST_DB_NAME).render_as_string(hide_password=False)
    command.upgrade(_alembic_config(url), "head")
    return url


@pytest.fixture(scope="session")
def alembic_config(test_database_url: str) -> Config:
    return _alembic_config(test_database_url)


@pytest.fixture(scope="session")
def engine(test_database_url: str) -> Iterator[Engine]:
    engine = create_engine(test_database_url, pool_pre_ping=True)
    yield engine
    engine.dispose()


@pytest.fixture(scope="session")
def session_factory(engine: Engine) -> sessionmaker[Session]:
    return sessionmaker(bind=engine, expire_on_commit=False)


@pytest.fixture
def session(engine: Engine, session_factory: sessionmaker[Session]) -> Iterator[Session]:
    with engine.begin() as connection:
        connection.execute(text("TRUNCATE TABLE appointments, physicians, medical_centers"))
    with session_factory() as db:
        yield db
